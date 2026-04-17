import re

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "r", encoding="utf-8") as f:
    code = f.read()

# Fix duplicates from prior failed replaces
code = code.replace("bg-[#F4F4F5] dark:bg-[#F4F4F5] dark:bg-surface-container-low border border-outline-variant/10",
                    "bg-[#ffffff] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10")

code = code.replace("bg-[#F4F4F5] dark:bg-[#F4F4F5] dark:bg-surface-container-low border border-black/10 dark:border-outline-variant/10",
                    "bg-[#ffffff] dark:bg-surface-container-lowest border border-black/10 dark:border-outline-variant/10")

# Fix intelligence engine text
code = code.replace('text-[11px] text-[#A3E635] opacity-50',
                    'text-[11px] text-[#65a30d] dark:text-[#A3E635] opacity-50 dark:opacity-50')
code = code.replace('bg-white dark:bg-[#0D0D0F] border-l-2',
                    'bg-[#f3f4f6] dark:bg-[#0D0D0F] border-l-2')

# Fix text on Health tracking elements
code = code.replace('text-[10px] uppercase tracking-[0.2em] font-bold"', 'text-[10px] text-[#18181B] dark:text-[#F8F9FA] uppercase tracking-[0.2em] font-bold"')
code = code.replace('tracking-[0.2em] font-bold">System Log Stream', 'tracking-[0.2em] font-bold text-[#18181B] dark:text-[#e5e1e4]">System Log Stream')

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "w", encoding="utf-8") as f:
    f.write(code)

print("App.jsx cleaned")
