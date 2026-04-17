import re

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Revert all the orange button changes
code = code.replace("bg-[#ea580c]/10 dark:bg-[#FF6B00]/10", "bg-[#FF6B00]/10")
code = code.replace("bg-[#ea580c] dark:bg-[#FF6B00]", "bg-[#FF6B00]")
code = code.replace("text-[#ea580c] dark:text-[#FF6B00]", "text-[#FF6B00]")
code = code.replace("border-[#ea580c]/30 dark:border-[#FF6B00]/30", "border-[#FF6B00]/30")
code = code.replace("selection:bg-[#ea580c]/30 dark:selection:bg-primary-container/30", "selection:bg-primary-container/30")

# 2. Make sure the background is clearly white in light mode, not grey
code = code.replace("bg-[#F4F4F5] dark:bg-[#0D0D0F]", "bg-white dark:bg-[#0D0D0F]")

# Fix index.html body class as well
with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/index.html", "r", encoding="utf-8") as f:
    html = f.read()

html = html.replace('bg-[#F4F4F5]', 'bg-white')
html = html.replace('text-[#18181B]', 'text-black')

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/index.html", "w", encoding="utf-8") as f:
    f.write(html)

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "w", encoding="utf-8") as f:
    f.write(code)

print("Restored orange colors. Fixed white background.")
