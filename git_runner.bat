# Initialize the local directory as a Git repository
git init

# Add all current files to the staging area
git add .

# Save the snapshot with an initial commit message
git commit -m "Initial project setup and source code commit"

# Rename the default branch to 'main' (modern Git standard)
git branch -M main

# Link the local repository to the remote GitHub server
git remote add origin https://github.com/AvvioPC2/AvvioPC_PrintDaemon.git

# Push the code to GitHub and set upstream tracking for future pushes
git push -u origin main