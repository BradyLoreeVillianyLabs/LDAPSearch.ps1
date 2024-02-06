## when running in powershell you must first enter the command "powershell -ep bypass" to allow powershell to run scripts. 

Enumeration.ps1

The script AD enumeration.ps1 is designed for Active Directory (AD) enumeration using PowerShell. It bypasses execution policy restrictions to run, retrieves the current domain's PDC (Primary Domain Controller) role owner, and constructs an LDAP path to query AD objects. It specifically searches for user objects by filtering on samAccountType=805306368(*can be changed) to enumerate them. 

LDAPSearchFunction.ps1

The LDAPSearch function in the PowerShell script is designed for Active Directory enumeration. It queries AD objects based on a given LDAP query string. The script retrieves the domain's Primary Domain Controller and constructs an LDAP path to search AD objects. Usage examples demonstrate how to call LDAPSearch with specific queries for groups or user objects. 
