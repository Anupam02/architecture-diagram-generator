This folder is the **Use Case 2** app. It belongs in
https://github.com/Anupam02/architecture-diagram-generator

This cloud agent could not push to that repository (GitHub 403: token is
limited to cv-competency-reviewer). To publish it:

```bash
cd architecture-diagram-generator
git init -b main
git add .
git commit -m "Add architecture diagram generator from technical notes"
git remote add origin https://github.com/Anupam02/architecture-diagram-generator.git
git push -u origin main
```

Then delete this folder from the competency-reviewer repo so Use Case 1 stays separate.
