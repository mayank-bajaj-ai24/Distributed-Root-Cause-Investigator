import re

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "r", encoding="utf-8") as f:
    code = f.read()

replacements = {
    # Main container wrappers
    "bg-surface-container-low": "bg-[#F4F4F5] dark:bg-surface-container-low",
    "bg-surface-container-lowest": "bg-white dark:bg-surface-container-lowest",
    "bg-surface-container-high": "bg-[#E4E4E7] dark:bg-surface-container-high",
    "bg-surface-container": "bg-[#F4F4F5] dark:bg-surface-container",
    
    # Let's fix the text overrides on the SYSTEM OVERVIEW area (currently lines 242-265 lack dark: tags for text)
    'text-3xl font-headline font-bold tracking-tight uppercase': 'text-3xl font-headline font-bold text-black dark:text-white tracking-tight uppercase',
    '<div className="text-3xl font-headline font-bold">11</div>': '<div className="text-3xl font-headline font-bold text-black dark:text-white">11</div>',
}

for old, new in replacements.items():
    code = code.replace(old, new)

# One edge case from before: The root App bg is still bg-background which is hardcoded black.
code = code.replace('className="min-h-screen bg-background text-[#18181B] dark:text-on-surface font-body selection:bg-primary-container/30"',
                    'className="min-h-screen bg-[#FAFAFA] dark:bg-background text-[#18181B] dark:text-on-surface font-body selection:bg-primary-container/30"')

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "w", encoding="utf-8") as f:
    f.write(code)

print("App.jsx component backgrounds fixed for light mode!")
