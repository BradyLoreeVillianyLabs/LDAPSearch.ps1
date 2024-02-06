The script AD enumeration.ps1 is designed for Active Directory (AD) enumeration using PowerShell. It bypasses execution policy restrictions to run, retrieves the current domain's PDC (Primary Domain Controller) role owner, and constructs an LDAP path to query AD objects. It specifically searches for user objects by filtering on samAccountType=805306368(*can be changed) to enumerate them. To document this script, a README should include its purpose, usage instructions (including the need to run PowerShell with -ep bypass), and a description of each section of the script (domain and PDC retrieval, LDAP path construction, and AD object enumeration).
