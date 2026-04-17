import re

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/index.css", "r", encoding="utf-8") as f:
    css = f.read()

# Current :root is actually dark mode. Let's rename it to .dark, and create a new :root for light mode.
light_mode_root = """:root {
  /* Light Core palette */
  --bg-primary: #f3f4f6;      
  --bg-secondary: #ffffff;    
  --bg-tertiary: #e5e7eb;     
  --bg-card: #ffffff;
  --bg-card-hover: #f9fafb;
  --bg-glass: rgba(255, 255, 255, 0.95);

  /* Borders */
  --border-subtle: rgba(0, 0, 0, 0.05);
  --border-medium: rgba(0, 0, 0, 0.1);
  --border-accent: rgba(59, 130, 246, 0.5); 

  /* Text */
  --text-primary: #111827;    
  --text-secondary: #4b5563;  
  --text-tertiary: #6b7280;   
  --text-inverse: #ffffff;

  /* Accent colors */
  --accent-blue: #2563eb;     
  --accent-blue-dim: rgba(37, 99, 235, 0.1);
  --accent-magenta: #dc2626;  
  --accent-magenta-dim: rgba(220, 38, 38, 0.1);
  --accent-emerald: #059669;  
  --accent-emerald-dim: rgba(5, 150, 105, 0.1);
  --accent-amber: #d97706;    
  --accent-amber-dim: rgba(217, 119, 6, 0.1);
  --accent-purple: #7c3aed;   
  --accent-purple-dim: rgba(124, 58, 237, 0.1);

  /* Status */
  --status-healthy: #059669;
  --status-warning: #d97706;
  --status-critical: #dc2626;
  --status-info: #2563eb;

  /* Gradients (Replaced with solids) */
  --gradient-blue: #2563eb;
  --gradient-magenta: #dc2626;
  --gradient-emerald: #059669;

  /* Shadows (Muted) */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  --shadow-glow-blue: none;
  --shadow-glow-magenta: none;
  --shadow-glow-emerald: none;

  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;

  /* Radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;

  /* Transitions */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 400ms cubic-bezier(0.4, 0, 0.2, 1);

  /* Typography */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}

.dark {
  /* Dark Core palette */"""

css = css.replace(":root {", light_mode_root)
# The spacing variables and others will be duplicated in .dark, which is fine since they are identical overrides, but let's just make it work.

with open("c:/Users/mayan/OneDrive/Desktop/HACK/frontend/src/index.css", "w", encoding="utf-8") as f:
    f.write(css)

print("index.css updated!")
