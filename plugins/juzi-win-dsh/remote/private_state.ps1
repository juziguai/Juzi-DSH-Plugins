param(
    [Parameter(Mandatory)][string]$Directory,
    [string]$UserSid = ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
)
$ErrorActionPreference = 'Stop'
$authorized = @($UserSid, 'S-1-5-18', 'S-1-5-32-544')
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true, $false)
if ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne $UserSid) {
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
}
foreach ($identity in $authorized) {
    $sid = [Security.Principal.SecurityIdentifier]::new($identity)
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        $sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
}
# Windows PowerShell 5.1 creates the directory with this DACL in one operation.
$dir = [IO.Directory]::CreateDirectory($Directory, $acl)
if ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unsafe state directory link' }
$actual = $dir.GetAccessControl()
$sidType = [Security.Principal.SecurityIdentifier]
if (-not $actual.AreAccessRulesProtected -or $actual.GetOwner($sidType).Value -notin $authorized) {
    throw 'Unsafe state directory owner or inherited permissions'
}
$rules = $actual.GetAccessRules($true, $true, $sidType)
foreach ($rule in $rules) {
    if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin $authorized) {
        throw 'Unsafe state directory permissions'
    }
}
