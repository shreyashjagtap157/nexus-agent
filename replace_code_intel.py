import sys

def replace_in_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    if filepath == 'src/nexus_agent/tools/code_intel.py':
        # E501 Line too long (123 > 100)
        content = content.replace("            return f\"Successfully renamed '{old_symbol}' to '{new_symbol}' ({replacements} replacements) in `{file_path}`.\"",
            "            return (\n                f\"Successfully renamed '{old_symbol}' to '{new_symbol}' \"\n                f\"({replacements} replacements) in `{file_path}`.\"\n            )")

        content = content.replace("            # fallback to simple regex rename if ast unparse has quirks or is python version specific",
            "            # fallback to regex rename if ast unparse has quirks")

        content = content.replace("                return f\"Successfully updated symbol '{old_symbol}' to '{new_symbol}' ({count} regex replacements) in `{file_path}`.\"",
            "                return (\n                    f\"Successfully updated symbol '{old_symbol}' to '{new_symbol}' \"\n                    f\"({count} regex replacements) in `{file_path}`.\"\n                )")

    with open(filepath, 'w') as f:
        f.write(content)

replace_in_file('src/nexus_agent/tools/code_intel.py')
