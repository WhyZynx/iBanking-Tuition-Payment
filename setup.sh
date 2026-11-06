#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
PROJECT="ibanking-demo"
FRONTEND_URL="http://localhost:8080"
MAILPIT_URL="http://localhost:8025"

fail() {
  printf '\nSetup failed: %s\n' "$1" >&2
  printf 'Troubleshooting: docker compose --env-file .env.docker -p %s logs --tail=80\n' "$PROJECT" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker CLI was not found. Install Docker Desktop or Docker Engine."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is unavailable. Update Docker Desktop."
docker info >/dev/null 2>&1 || fail "Docker Engine is not running. Start Docker Desktop and retry."

if [[ ! -f .env.docker ]]; then
  command -v od >/dev/null 2>&1 || fail "The standard od utility is unavailable; cannot generate secure secrets."
  [[ -f .env.docker.example ]] || fail ".env.docker.example template is missing."
  umask 077
  secret_mysql="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
  secret_jwt="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
  secret_internal="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
  if ! (set -o noclobber; awk \
    -v mysql="$secret_mysql" -v jwt="$secret_jwt" -v internal="$secret_internal" \
    '/^MYSQL_ROOT_PASSWORD=/ { print "MYSQL_ROOT_PASSWORD=" mysql; next }
     /^JWT_SECRET_KEY=/ { print "JWT_SECRET_KEY=" jwt; next }
     /^INTERNAL_API_KEY=/ { print "INTERNAL_API_KEY=" internal; next }
     { print }' .env.docker.example > .env.docker); then
    unset secret_mysql secret_jwt secret_internal
    fail "Could not create .env.docker without overwriting another file."
  fi
  unset secret_mysql secret_jwt secret_internal
  chmod 600 .env.docker 2>/dev/null || true
  printf 'Created .env.docker with private random development secrets.\n'
fi

if ! grep -Eq '^MYSQL_ROOT_PASSWORD=.+$' .env.docker \
  || ! grep -Eq '^JWT_SECRET_KEY=.+$' .env.docker \
  || ! grep -Eq '^INTERNAL_API_KEY=.+$' .env.docker; then
  fail ".env.docker is missing a required secret. Restore the required keys without sharing their values."
fi
if grep -Eq '^(MYSQL_ROOT_PASSWORD|JWT_SECRET_KEY|INTERNAL_API_KEY)=(GENERATE_WITH_SETUP_SCRIPT|change_this.*|change-this.*)$' .env.docker; then
  fail ".env.docker contains an example placeholder. Keep the file, replace only its placeholder secret values with secure random values, and retry."
fi

docker compose --env-file .env.docker -p "$PROJECT" config --quiet \
  || fail "Compose configuration is invalid. Check .env.docker and docker-compose.yml."

printf 'Building and starting iBanking services. Existing Docker volumes are preserved.\n'
if ! docker compose --env-file .env.docker -p "$PROJECT" up --build --detach --wait --wait-timeout 240; then
  fail "A container failed to build or become healthy. Check the logs command shown above. If a host port is occupied, set FRONTEND_PORT or MAILPIT_WEB_PORT in .env.docker."
fi

frontend_port="$(sed -n 's/^FRONTEND_PORT=//p' .env.docker | tail -n 1)"
mailpit_port="$(sed -n 's/^MAILPIT_WEB_PORT=//p' .env.docker | tail -n 1)"
[[ "$frontend_port" =~ ^[0-9]{1,5}$ ]] || frontend_port=8080
[[ "$mailpit_port" =~ ^[0-9]{1,5}$ ]] || mailpit_port=8025
FRONTEND_URL="http://localhost:${frontend_port}"
MAILPIT_URL="http://localhost:${mailpit_port}"
curl --fail --silent --show-error --max-time 5 "http://127.0.0.1:${frontend_port}/" >/dev/null \
  || fail "Nginx/frontend did not answer on port ${frontend_port}. Check the container logs and port availability."
curl --fail --silent --show-error --max-time 5 "http://127.0.0.1:${mailpit_port}/" >/dev/null \
  || fail "Mailpit did not answer on port ${mailpit_port}. Check the container logs and port availability."
login_status="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 \
  -H 'Content-Type: application/json' \
  --data '{"username":"user01","password":"password123"}' \
  "http://127.0.0.1:${frontend_port}/api/v1/auth/login" || true)"
[[ "$login_status" == "200" ]] || fail "The demo login check failed (HTTP ${login_status:-no response}); check database seeding and User Service logs."

printf '\n========================================\n iBanking Setup Completed Successfully\n========================================\n\n'
printf 'Frontend: http://localhost:%s\n' "$frontend_port"
printf 'Demo Email Inbox: http://localhost:%s\n\n' "$mailpit_port"
printf 'Services: User Service READY; Tuition Service READY; Payment Service READY; MySQL READY; Nginx READY; Mailpit READY\n\n'
printf 'Demo Login: user01 / password123\n\nTo stop: ./stop.sh\nTo restart: ./setup.sh\n'

view_demo_data() {
  local query_file="$ROOT_DIR/db/demo-data-view.sql"
  if [[ ! -f "$query_file" ]]; then
    printf 'Demo data query file is missing.\n' >&2
  elif ! docker compose --env-file .env.docker -p "$PROJECT" exec -T mysql \
    sh -c 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -uroot --table' < "$query_file"; then
    printf 'Could not read current demo data. Check that MySQL is running and initialized.\n' >&2
    printf 'Troubleshooting: docker compose --env-file .env.docker -p %s logs --tail=80 mysql\n' "$PROJECT" >&2
  fi
  printf '\nPress Enter to return to the menu.'
  IFS= read -r _ || true
}

open_url() {
  local url="$1"
  if [[ "$OSTYPE" == msys* || "$OSTYPE" == cygwin* ]]; then
    cmd.exe /c start "" "$url" >/dev/null 2>&1 || printf 'Open this URL in your browser: %s\n' "$url"
  elif [[ "$OSTYPE" == darwin* ]]; then
    open "$url" >/dev/null 2>&1 || printf 'Open this URL in your browser: %s\n' "$url"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || printf 'Open this URL in your browser: %s\n' "$url"
  else
    printf 'Open this URL in your browser: %s\n' "$url"
  fi
}

apply_smtp_config() {
  local mode="$1" smtp_host smtp_port smtp_username smtp_password smtp_from smtp_starttls
  local old_file temp_file
  if [[ "$mode" == gmail ]]; then
    printf '\nGmail requires Google 2-Step Verification and a Google App Password.\n'
    printf 'The App Password will be hidden and stored only in the ignored .env.docker file.\n'
    read -r -p 'Gmail sender address: ' smtp_username
    [[ "$smtp_username" =~ ^[^[:space:]@]+@gmail\.com$ ]] || { printf 'Enter a valid @gmail.com sender address.\n'; return 1; }
    read -r -s -p 'Gmail App Password: ' smtp_password
    printf '\n'
    smtp_password="${smtp_password// /}"
    [[ -n "$smtp_password" ]] || { printf 'An App Password is required.\n'; unset smtp_password; return 1; }
    smtp_host='smtp.gmail.com'; smtp_port=587; smtp_from="$smtp_username"; smtp_starttls=true
  else
    smtp_host=mailpit; smtp_port=1025; smtp_username=; smtp_password=; smtp_from=ibanking@example.test; smtp_starttls=false
  fi

  export IBANKING_SMTP_HOST="$smtp_host" IBANKING_SMTP_PORT="$smtp_port"
  export IBANKING_SMTP_USERNAME="$smtp_username" IBANKING_SMTP_PASSWORD="$smtp_password"
  export IBANKING_SMTP_FROM_EMAIL="$smtp_from" IBANKING_SMTP_STARTTLS="$smtp_starttls"
  old_file="$(mktemp)" || { unset IBANKING_SMTP_PASSWORD smtp_password; return 1; }
  temp_file="$(mktemp)" || { rm -f "$old_file"; unset IBANKING_SMTP_PASSWORD smtp_password; return 1; }
  cp .env.docker "$old_file"
  if ! chmod 600 "$old_file" "$temp_file" 2>/dev/null; then
    printf 'Could not secure temporary SMTP configuration files; no settings were changed.\n' >&2
    rm -f "$old_file" "$temp_file"
    unset IBANKING_SMTP_HOST IBANKING_SMTP_PORT IBANKING_SMTP_USERNAME IBANKING_SMTP_PASSWORD IBANKING_SMTP_FROM_EMAIL IBANKING_SMTP_STARTTLS smtp_password
    return 1
  fi
  if ! awk '
    BEGIN { keys["SMTP_HOST"]=1; keys["SMTP_PORT"]=1; keys["SMTP_USERNAME"]=1; keys["SMTP_PASSWORD"]=1; keys["SMTP_FROM_EMAIL"]=1; keys["SMTP_STARTTLS"]=1 }
    /^SMTP_HOST=/ { print "SMTP_HOST=" ENVIRON["IBANKING_SMTP_HOST"]; seen["SMTP_HOST"]=1; next }
    /^SMTP_PORT=/ { print "SMTP_PORT=" ENVIRON["IBANKING_SMTP_PORT"]; seen["SMTP_PORT"]=1; next }
    /^SMTP_USERNAME=/ { print "SMTP_USERNAME=" ENVIRON["IBANKING_SMTP_USERNAME"]; seen["SMTP_USERNAME"]=1; next }
    /^SMTP_PASSWORD=/ { print "SMTP_PASSWORD=" ENVIRON["IBANKING_SMTP_PASSWORD"]; seen["SMTP_PASSWORD"]=1; next }
    /^SMTP_FROM_EMAIL=/ { print "SMTP_FROM_EMAIL=" ENVIRON["IBANKING_SMTP_FROM_EMAIL"]; seen["SMTP_FROM_EMAIL"]=1; next }
    /^SMTP_STARTTLS=/ { print "SMTP_STARTTLS=" ENVIRON["IBANKING_SMTP_STARTTLS"]; seen["SMTP_STARTTLS"]=1; next }
    { print }
    END { for (key in keys) if (!seen[key]) print key "=" ENVIRON["IBANKING_" key] }
  ' .env.docker > "$temp_file"; then
    printf 'Could not prepare the SMTP configuration.\n' >&2
    cp "$old_file" .env.docker
    rm -f "$old_file" "$temp_file"
    unset IBANKING_SMTP_HOST IBANKING_SMTP_PORT IBANKING_SMTP_USERNAME IBANKING_SMTP_PASSWORD IBANKING_SMTP_FROM_EMAIL IBANKING_SMTP_STARTTLS smtp_password
    return 1
  fi
  if ! chmod 600 "$temp_file" 2>/dev/null; then
    printf 'Could not secure the updated SMTP configuration; previous settings were preserved.\n' >&2
    cp "$old_file" .env.docker
    rm -f "$old_file" "$temp_file"
    unset IBANKING_SMTP_HOST IBANKING_SMTP_PORT IBANKING_SMTP_USERNAME IBANKING_SMTP_PASSWORD IBANKING_SMTP_FROM_EMAIL IBANKING_SMTP_STARTTLS smtp_password
    return 1
  fi
  mv -f "$temp_file" .env.docker
  if docker compose --env-file .env.docker -p "$PROJECT" up -d --no-deps --wait --wait-timeout 120 payment-service >/dev/null 2>&1; then
    rm -f "$old_file"
    if [[ "$mode" == gmail ]]; then
      printf 'Gmail SMTP configuration applied to Payment Service. Delivery has not been tested.\n'
      printf 'OTP still goes to the paying user email in the database.\n'
    else
      printf 'Mailpit configuration applied to Payment Service.\n'
    fi
  else
    cp "$old_file" .env.docker
    docker compose --env-file .env.docker -p "$PROJECT" up -d --no-deps --wait --wait-timeout 120 payment-service >/dev/null 2>&1 || true
    rm -f "$old_file"
    printf 'SMTP configuration could not be applied. The previous settings were restored.\n' >&2
    unset IBANKING_SMTP_HOST IBANKING_SMTP_PORT IBANKING_SMTP_USERNAME IBANKING_SMTP_PASSWORD IBANKING_SMTP_FROM_EMAIL IBANKING_SMTP_STARTTLS smtp_password
    return 1
  fi
  unset IBANKING_SMTP_HOST IBANKING_SMTP_PORT IBANKING_SMTP_USERNAME IBANKING_SMTP_PASSWORD IBANKING_SMTP_FROM_EMAIL IBANKING_SMTP_STARTTLS smtp_password
}

show_email_menu() {
  local current_host choice
  while true; do
    current_host="$(sed -n 's/^SMTP_HOST=//p' .env.docker | tail -n 1)"
    case "$current_host" in smtp.gmail.com) current_host='Gmail SMTP' ;; mailpit) current_host=Mailpit ;; *) current_host='Custom SMTP' ;; esac
    printf '\n========================================\n Email Delivery Configuration\n========================================\nCurrent Mode: %s\n[1] Use Mailpit (Local Testing)\n[2] Use Gmail SMTP (Real Email)\n[0] Back to Main Menu\n' "$current_host"
    read -r -p 'Choose an option: ' choice || return 0
    case "$choice" in
      1) apply_smtp_config mailpit && return 0 ;;
      2) apply_smtp_config gmail && return 0 ;;
      0) return 0 ;;
      *) printf 'Please enter 1, 2, or 0.\n' ;;
    esac
  done
}

prepare_test_environment() {
  local test_script="$ROOT_DIR/setup-tests.sh"
  if [[ ! -f "$test_script" ]]; then
    printf 'setup-tests.sh is missing.\n' >&2
    return 1
  fi
  bash "$test_script" prepare
  printf '\nPress Enter to return to the Tests menu.'
  IFS= read -r _ || true
}

run_automated_tests() {
  local test_script="$ROOT_DIR/setup-tests.sh"
  if [[ ! -f "$test_script" ]]; then
    printf 'setup-tests.sh is missing.\n' >&2
  elif [[ ! -x "$ROOT_DIR/.venv-ibanking-tests/bin/python" ]]; then
    printf 'Test environment is not prepared. Choose [1] first.\n'
  else
    bash "$test_script" run || printf 'Automated tests failed. Review the output above.\n'
  fi
  printf '\nPress Enter to return to the Tests menu.'
  IFS= read -r _ || true
}

run_concurrency_test() {
  local test_path="$1" approval previous_approval had_previous=0 exit_code=0
  local python_path="$ROOT_DIR/.venv-ibanking-tests/bin/python"
  printf '\n'
  if [[ ! -x "$python_path" ]]; then
    printf 'Test environment is not prepared. Choose [1] Prepare test environment first.\n'
    printf 'Press Enter to return to the Concurrency menu.'
    IFS= read -r _ || true
    return 0
  fi
  if [[ ! -f "$ROOT_DIR/$test_path" ]]; then
    printf 'Concurrency test file is missing: %s\n' "$test_path" >&2
    return 1
  fi
  printf 'WARNING: This test may modify the demo database.\n'
  printf 'It can create transactions, debit demo accounts, and mark tuition as PAID.\n'
  read -r -p 'Continue? (Y/N): ' approval || return 0
  case "$approval" in
      Y|y|YES|Yes|yes)
          ;;
      *)
          echo "Test cancelled."
          return
          ;;
  esac
  if [[ ${IBANKING_DEMO_CONCURRENCY_APPROVAL+x} ]]; then
    had_previous=1
    previous_approval="$IBANKING_DEMO_CONCURRENCY_APPROVAL"
  fi
  export IBANKING_DEMO_CONCURRENCY_APPROVAL=YES
  printf '\nRunning: %s\n----------------------------------------\n' "$test_path"
  "$python_path" -m pytest "$ROOT_DIR/$test_path" -m demo_live -v -s || exit_code=$?
  if (( had_previous )); then
    export IBANKING_DEMO_CONCURRENCY_APPROVAL="$previous_approval"
  else
    unset IBANKING_DEMO_CONCURRENCY_APPROVAL
  fi
  if (( exit_code == 0 )); then
    printf '\nTest completed successfully.\n'
  else
    printf '\nTest finished with exit code %s.\n' "$exit_code"
  fi
  printf 'Press Enter to return to the Concurrency menu.'
  IFS= read -r _ || true
}

show_concurrency_menu() {
  local choice
  while true; do
    printf '\n========================================\n Concurrency Testing\n========================================\n[1] Same Account - Two Students\n[2] Two Payer - Same Student\n[3] Run Both Tests\n[0] Back to Tests Menu\n'
    read -r -p 'Choose an option: ' choice || return 0
    case "$choice" in
      1) run_concurrency_test 'tests/payment_service/test_payment_concurrency_same_account.py' ;;
      2) run_concurrency_test 'tests/payment_service/test_demo_two_payer_concurrency.py' ;;
      3)
        run_concurrency_test 'tests/payment_service/test_payment_concurrency_same_account.py'
        run_concurrency_test 'tests/payment_service/test_demo_two_payer_concurrency.py'
        ;;
      0) return 0 ;;
      *) printf 'Please enter 1, 2, 3, or 0.\n' ;;
    esac
  done
}

show_tests_menu() {
  local choice
  while true; do
    printf '\n========================================\n Tests\n========================================\n[1] Prepare test environment\n[2] Run automated tests\n[3] Run concurrency tests\n[0] Back to Main Menu\n'
    read -r -p 'Choose an option: ' choice || return 0
    case "$choice" in
      1) prepare_test_environment ;;
      2) run_automated_tests ;;
      3) show_concurrency_menu ;;
      0) return 0 ;;
      *) printf 'Please enter 1, 2, 3, or 0.\n' ;;
    esac
  done
}

if [[ -t 0 && -t 1 ]]; then
  while true; do
    printf '\n[1] View current demo data\n[2] Open iBanking frontend\n[3] Open Mailpit inbox\n[4] Configure email delivery\n[5] Tests\n[0] Exit setup (keep services running)\n'
    printf 'Choose an option: '
    IFS= read -r choice || exit 0
    case "$choice" in
      1) view_demo_data ;;
      2) open_url "$FRONTEND_URL" ;;
      3) open_url "$MAILPIT_URL" ;;
      4) show_email_menu ;;
      5) show_tests_menu ;;
      0) break ;;
      *) printf 'Please enter 1, 2, 3, 4, 5, or 0.\n' ;;
    esac
  done
fi
