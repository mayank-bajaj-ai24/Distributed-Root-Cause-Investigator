import re

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "r", encoding="utf-8") as f:
    code = f.read()

replacements = {
    # Backgrounds
    "bg-[#16161A]": "bg-[#FFFFFF] dark:bg-[#16161A]",
    "bg-[#0D0D0F]": "bg-[#F4F4F5] dark:bg-[#0D0D0F]",
    "bg-[#FF6B00]/10": "bg-[#ea580c]/10 dark:bg-[#FF6B00]/10",
    "bg-[#FF6B00]": "bg-[#ea580c] dark:bg-[#FF6B00]",
    
    # Texts
    "text-[#FF6B00]": "text-[#ea580c] dark:text-[#FF6B00]",
    "text-[#0D0D0F]": "text-[#ffffff] dark:text-[#0D0D0F]",
    "text-[#8E9196]": "text-[#52525B] dark:text-[#8E9196]",
    "text-on-surface": "text-[#18181B] dark:text-on-surface",
    "text-secondary": "text-[#3F3F46] dark:text-secondary",
    
    # Borders
    "border-[#FF6B00]/5": "border-black/5 dark:border-[#FF6B00]/5",
    "border-[#FF6B00]/10": "border-black/10 dark:border-[#FF6B00]/10",
    "border-[#FF6B00]/30": "border-[#ea580c]/30 dark:border-[#FF6B00]/30",
    "border-outline-variant/20": "border-black/10 dark:border-outline-variant/20",
    
    # Selection
    "selection:bg-primary-container/30": "selection:bg-[#ea580c]/30 dark:selection:bg-primary-container/30",
}

for old, new in replacements.items():
    code = code.replace(old, new)

# Theme toggle button
header_button_insert = """            <button
              onClick={toggleTheme}
              className="px-3 py-1 bg-white dark:bg-[#16161A] border border-black/10 dark:border-[#FF6B00]/30 rounded-sm text-xs font-bold uppercase tracking-widest text-[#18181B] dark:text-[#FF6B00] hover:bg-gray-100 dark:hover:bg-[#FF6B00]/20 transition-all"
            >
              {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
            </button>
            <div className="flex items-center gap-2 px-3 py-1 border border-black/10 dark:border-[#FF6B00]/30 rounded-sm">"""

code = code.replace("""          <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 border border-[#FF6B00]/30 rounded-sm">""", 
          """          <div className="flex items-center gap-4">""" + "\n" + header_button_insert)

# Fallback for the replaced text from earlier if needed
code = code.replace("""        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 border border-black/10 dark:border-[#FF6B00]/30 rounded-sm">""",
          """        <div className="flex items-center gap-4">""" + "\n" + header_button_insert)

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/App.jsx", "w", encoding="utf-8") as f:
    f.write(code)

print("App.jsx refactored for light mode!")
