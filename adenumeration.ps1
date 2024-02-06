
#AD enumeration.ps1
#powershell -ep bypass   __ to execute scripts in powershell. __

# Store the domain object in the $domainObj variable
$domainObj = [System.DirectoryServices.ActiveDirectory.Domain]::GetCurrentDomain()

# Store the PdcRoleOwner name to the $PDC variable
$PDC = $domainObj.PdcRoleOwner.name

#print the PdcRoleOwner 
#$PDC 

# Store the Distinguished Name into the $DN variable
$DN = ([adsi]'').distinguishedName

# Print the $DN variable
#$DN

# Assemble the pieces into proper naming convention
$LDAP = "LDAP://$PDC/$DN"

# Print LDAP variable
#$LDAP
$direntry = New-Object System.DirectoryServices.DirectoryEntry($LDAP)
$dirsearcher = New-Object System.DirectoryServices.DirectorySearcher($direntry)
$dirsearcher.filter="samAccountType=805306368" #jeffadmin** 
$dirsearcher.FindAll()
ForEach($obj in $result)
{
        ForEach($prop in $obj.Properties)
        {
            $prop #.memberof **
        }
        Write-Host "----------------------------"
}
 
