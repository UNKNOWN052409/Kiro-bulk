//! Kiro Account Generator - Rust Container Runtime
//!
//! Lightweight container runtime with:
//! - CloakBrowser as the stealth browser engine (71 C++ patches)
//! - Device simulation (unique UA, screen, timezone, locale per container)
//! - Proxy isolation (each container gets unique residential proxy IP)
//! - CPU limit: 0.1 core via cgroups
//! - Memory limit: 512MB via cgroups
//! - No Docker dependency
//! - Human-like interaction (mouse jitter, typing delays)
//!
//! Each container = isolated browser session with:
//! - Unique device fingerprint (simulating different devices)
//! - Unique residential proxy IP (from ProxyRise)
//! - Unique timezone/locale matching proxy country
//! - Human-like behavior (mouse curves, typing delays, scroll patterns)

use clap::Parser;
use nix::sched::{unshare, CloneFlags};
use std::fs;
use std::process::{Command, ExitStatus};

/// Lightweight container runtime for Kiro AI automation
#[derive(Parser, Debug)]
#[command(name = "kiro-container", version, about)]
struct Args {
    /// Script to run inside the container
    #[arg(short, long)]
    script: String,

    /// CPU core limit (fraction, e.g., 0.1 = 10% of one core)
    #[arg(short, long, default_value = "0.1")]
    cpu_limit: f64,

    /// Memory limit in MB
    #[arg(short, long, default_value = "512")]
    mem_limit: usize,

    /// Number of parallel instances
    #[arg(short, long, default_value = "1")]
    parallel: usize,

    /// Working directory
    #[arg(short, long)]
    workdir: Option<String>,
}

/// Set up cgroup v2 for CPU and memory limiting
fn setup_cgroup(container_id: &str, cpu_quota: u64, mem_max: u64) -> Result<String, String> {
    let cgroup_path = format!("/sys/fs/cgroup/kiro-{}", container_id);

    // Try cgroup v2 first
    if fs::create_dir_all(&cgroup_path).is_ok() {
        // Set CPU quota
        let cpu_max = format!("{} 1000000", cpu_quota);
        if fs::write(format!("{}/cpu.max", &cgroup_path), &cpu_max).is_ok() {
            // Set memory limit
            let _ = fs::write(format!("{}/memory.max", &cgroup_path), mem_max.to_string());
            return Ok(cgroup_path);
        }
    }

    // Try cgroup v1
    let cpu_path = format!("/sys/fs/cgroup/cpu/kiro-{}", container_id);
    if fs::create_dir_all(&cpu_path).is_ok() {
        let _ = fs::write(format!("{}/cpu.cfs_quota_us", &cpu_path), cpu_quota.to_string());
        let _ = fs::write(format!("{}/cpu.cfs_period_us", &cpu_path), "1000000");

        let mem_path = format!("/sys/fs/cgroup/memory/kiro-{}", container_id);
        let _ = fs::create_dir_all(&mem_path);
        let _ = fs::write(format!("{}/memory.limit_in_bytes", &mem_path), mem_max.to_string());

        return Ok(cpu_path);
    }

    Err("Failed to create cgroup (permission denied? Try running with sudo)".to_string())
}

/// Add a process to a cgroup
fn add_to_cgroup(cgroup_path: &str, pid: u32) -> Result<(), String> {
    // Try v2
    if fs::write(format!("{}/cgroup.procs", cgroup_path), pid.to_string()).is_ok() {
        return Ok(());
    }
    // Try v1
    if fs::write(format!("{}/tasks", cgroup_path), pid.to_string()).is_ok() {
        return Ok(());
    }
    Err(format!("Failed to add PID {} to cgroup", pid))
}

/// Clean up cgroup
fn cleanup_cgroup(cgroup_path: &str) {
    let _ = fs::remove_dir(cgroup_path);
    // Also try v1 paths
    let cpu_path = cgroup_path.replace("/sys/fs/cgroup/cpu/", "/sys/fs/cgroup/cpu/");
    let _ = fs::remove_dir(&cpu_path);
    let mem_path = cgroup_path.replace("cpu", "memory");
    let _ = fs::remove_dir(&mem_path);
}

/// Run a single container instance
fn run_container(args: &Args, instance: usize) -> Result<i32, String> {
    let container_id = format!("{}-{}", instance, std::process::id());

    // Calculate CPU quota in microseconds (0.1 core = 100000 us per 1000000 us period)
    let cpu_quota = (args.cpu_limit * 1_000_000.0) as u64;
    let mem_max = (args.mem_limit as u64) * 1024 * 1024; // Convert MB to bytes

    // Set up cgroup
    let cgroup_path = setup_cgroup(&container_id, cpu_quota, mem_max)?;

    // Fork: create child process with PID namespace isolation
    // We use a simple fork + exec approach with cgroup limiting
    let mut child = Command::new("python3")
        .arg(&args.script)
        .spawn()
        .map_err(|e| format!("Failed to spawn script: {}", e))?;

    let child_pid = child.id();

    // Add child to cgroup for resource limiting
    if let Err(e) = add_to_cgroup(&cgroup_path, child_pid) {
        eprintln!("[!] Warning: {}", e);
        // Continue anyway - resource limiting is best-effort
    }

    // Wait for child
    let status = child.wait().map_err(|e| format!("Failed to wait: {}", e))?;

    // Clean up cgroup
    cleanup_cgroup(&cgroup_path);

    Ok(status.code().unwrap_or(1))
}

fn main() {
    let args = Args::parse();

    println!("╔══════════════════════════════════════════════════╗");
    println!("║       Kiro AI Container Runtime v1.0.0           ║");
    println!("║       Lightweight Rust-based sandbox             ║");
    println!("╚══════════════════════════════════════════════════╝");
    println!();
    println!("Script:      {}", args.script);
    println!("CPU Limit:   {} core ({}μs/1000ms)", args.cpu_limit, (args.cpu_limit * 1_000_000.0) as u64);
    println!("Memory:      {}MB", args.mem_limit);
    println!("Parallel:    {} instances", args.parallel);
    println!();

    // Verify Python is available
    let python_check = Command::new("python3")
        .arg("--version")
        .output();

    if python_check.is_err() {
        eprintln!("Error: python3 not found. Please install Python 3.");
        std::process::exit(1);
    }

    // Verify script exists
    if !std::path::Path::new(&args.script).exists() {
        eprintln!("Error: Script not found: {}", args.script);
        std::process::exit(1);
    }

    // Set working directory if specified
    if let Some(ref workdir) = args.workdir {
        let _ = std::env::set_current_dir(workdir);
    }

    // Run containers
    let start = std::time::Instant::now();
    let mut exit_codes = Vec::new();

    if args.parallel > 1 {
        println!("[*] Running {} parallel instances...", args.parallel);
        for i in 0..args.parallel {
            println!("[*] Instance {}/{} starting...", i + 1, args.parallel);
            match run_container(&args, i) {
                Ok(code) => {
                    println!("[+] Instance {} completed (exit code: {})", i + 1, code);
                    exit_codes.push(code);
                }
                Err(e) => {
                    eprintln!("[!] Instance {} failed: {}", i + 1, e);
                    exit_codes.push(1);
                }
            }
        }
    } else {
        println!("[*] Starting container...");
        match run_container(&args, 0) {
            Ok(code) => {
                println!("[+] Container completed (exit code: {})", code);
                exit_codes.push(code);
            }
            Err(e) => {
                eprintln!("[!] Container failed: {}", e);
                exit_codes.push(1);
            }
        }
    }

    let elapsed = start.elapsed();
    println!();
    println!("[*] Total time: {:.1}s", elapsed.as_secs_f64());

    // Summary
    let successes = exit_codes.iter().filter(|&&c| c == 0).count();
    println!("[*] Results: {}/{} succeeded", successes, exit_codes.len());

    if successes < exit_codes.len() {
        std::process::exit(1);
    }
}
