import re

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "r", encoding="utf-8") as f:
    code = f.read()

# Make all the panels grayish in light mode to match the Service Overview panel
code = code.replace("bg-[#ffffff] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10",
                    "bg-[#f3f4f6] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10")

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "w", encoding="utf-8") as f:
    f.write(code)

print("Backgrounds normalized.")
