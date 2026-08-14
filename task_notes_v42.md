# Task Notes v42 - ERR-837 Investigation

## Problem
- Accounts created by the bot (ax3p0kzyk6, 3b6q9gvgrt, etc.) need a "Enter your name" page during sign-in
- After filling name and clicking Continue, AWS returns ERR-837: "Sorry, there was an error processing your request. Please try again."
- This happens consistently across multiple attempts, different methods (UI modal, direct API)
- The error is server-side from AWS Builder ID

## Root Cause Hypothesis
- ERR-837 in AWS Builder ID typically means the account's profile data is in an inconsistent state
- These accounts were created by the bot but the name field was never properly set during account creation
- The AWS server is rejecting the name submission because of some data inconsistency

## Working Accounts
- nicholas204@havenhaus.in - works (already has name set, no name page needed)

## Failed Accounts (need name page)
- ax3p0kzyk6@havenhaus.in
- 3b6q9gvgrt@havenhaus.in
- glenn64palmer@havenhaus.in
- wcb53bjea2@havenhaus.in
- o8rep9h8uk@havenhaus.in
- cgg0r7pfis@havenhaus.in
- d2yrlsw96i@havenhaus.in
- buco0ftwsn@havenhaus.in
- 5b717roxmg@havenhaus.in
- g13ue7snry@havenhaus.in
- tq5h1bobc7@havenhaus.in
- 34annrs3pc@havenhaus.in
- puizvy7pbk@havenhaus.in
- ipgxiccrw0@havenhaus.in
- ht9ja00wfd@havenhaus.in
- vhfvl3ka59@havenhaus.in
- m7rbu7ntqm@havenhaus.in
- vxk3w456dl@havenhaus.in
- powell707@havenhaus.in

## Possible Solutions
1. Try creating NEW accounts that properly set the name during creation
2. Try a different name format (maybe the name needs to be exactly what was used during creation)
3. Try skipping the name page by using a different auth method
4. The accounts might be salvageable if we can find a way to complete the name step

## Key Insight
The accounts that DON'T need a name page (nicholas204) were created differently from the ones that DO. The bot's account creation flow might have set the name for some accounts but not others.
