## 2024-05-18 - Fix command injection in Sandbox fallback
**Vulnerability:** The command isolation sandbox (`Sandbox.execute`) fell back to executing commands via `sh -c` or `powershell` with unparsed string commands when `shlex.split()` failed to parse due to unmatched quotes or syntax errors. This bypasses array-based shell escaping and presents a command injection vulnerability.
**Learning:** Fallbacks intended to improve developer experience (e.g., executing malformed strings in a subshell) can completely undermine the primary security isolation mechanism if they revert to inherently unsafe functions like `sh -c`.
**Prevention:** If the safe parsing mechanism (`shlex.split()`) fails to interpret input securely, the operation must be rejected entirely rather than passed on to a less secure evaluation layer.

## 2024-05-24 - Enhance machine ID generation for API key encryption
**Vulnerability:** Weak cryptography due to predictable key derivation. The `FernetFileBackend._init_fernet` method used `uuid.getnode()` (the machine's MAC address) to derive the encryption key for stored API credentials. MAC addresses are predictable, easily discoverable, and provide insufficient entropy for secure key generation. Furthermore, they can change frequently (e.g., VPNs, Docker interfaces), rendering the stored API keys inaccessible.
**Learning:** Using easily accessible hardware identifiers (like a MAC address) as the sole source of entropy for encryption keys compromises the security of data at rest.
**Prevention:** Always use cryptographically secure sources of entropy for key generation, or leverage robust, OS-level unique identifiers (like `/etc/machine-id` or Windows registry MachineGuid) when binding data to a specific machine.
