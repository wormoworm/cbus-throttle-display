# A deployment script that pushes the source code to a remote machine and then runs the chosen application.
# The stdout from the application is captured to help with debugging.

target=$1
install_dependencies=$2

dir_application=/home/pi/cbus-throttle-display

printf "Running deployment script, target is $target. Will install to $dir_application. Install dependencies = $install_dependencies\n"

# 1: Copy the application to the target.
printf "Copying application...\n"
scp -rq src pyproject.toml pi@$target:$dir_application

# 2: Update dependencies, if requested
if [ "$install_dependencies" = true ] ; then
    printf "Updating dependencies...\n"
    ssh pi@$target "cd $dir_application && poetry update"
fi

# 3: Run the application
printf "Running application...\n--------------------------------------------------\n"
ssh pi@$target "cd $dir_application && poetry run python -u src/main.py"