import re

# Read base.html
with open('templates/base.html', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Check for required function definitions
functions_to_check = [
    'toggleMessagingPanel',
    'switchMessagingTab',
    'sendQuickMessage',
    'openComposeTab',
    'toggleSidebar',
    'toggleSidebarCollapse'
]

print("Checking function definitions in base.html...")
print("=" * 60)

for func in functions_to_check:
    # Search for function definition
    pattern = rf'function {func}\s*\('
    if re.search(pattern, content):
        # Count occurrences of window.{func} = 
        window_pattern = rf'window\.{func}\s*='
        window_matches = len(re.findall(window_pattern, content))
        print(f"✅ {func}")
        print(f"   - Function defined: YES")
        print(f"   - Window exposure count: {window_matches}")
    else:
        print(f"❌ {func}")
        print(f"   - Function defined: NO")

print("=" * 60)

# Check for onclick patterns
print("\nChecking onclick patterns...")
print("=" * 60)

onclick_patterns = [
    'onclick="window.toggleMessagingPanel',
    'onclick="window.toggleSidebar',
    'onclick="window.sendQuickMessage'
]

for pattern in onclick_patterns:
    matches = content.count(pattern)
    if matches > 0:
        print(f"✅ {pattern}: Found {matches} times")
    else:
        print(f"❌ {pattern}: NOT FOUND")

print("\n" + "=" * 60)
print("✅ Analysis complete!")
