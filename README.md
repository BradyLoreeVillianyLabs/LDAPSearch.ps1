Enumeration.ps1

The script AD enumeration.ps1 is designed for Active Directory (AD) enumeration using PowerShell. It bypasses execution policy restrictions to run, retrieves the current domain's PDC (Primary Domain Controller) role owner, and constructs an LDAP path to query AD objects. It specifically searches for user objects by filtering on samAccountType=805306368(*can be changed) to enumerate them. To document this script, a README should include its purpose, usage instructions (including the need to run PowerShell with -ep bypass), and a description of each section of the script (domain and PDC retrieval, LDAP path construction, and AD object enumeration).

LDAPSearchFunction.ps1

The LDAPSearch function in the PowerShell script is designed for Active Directory enumeration. It queries AD objects based on a given LDAP query string. The script retrieves the domain's Primary Domain Controller and constructs an LDAP path to search AD objects. Usage examples demonstrate how to call LDAPSearch with specific queries for groups or user objects. This PowerShell function requires bypassing the execution policy (powershell -ep bypass) to run. It’s a powerful tool for system administrators to query and manage AD objects programmatically.
