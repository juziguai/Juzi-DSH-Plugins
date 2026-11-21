function Open-ReleaseStore([string]$Root, [switch]$Create) {
    $sidType = [Security.Principal.SecurityIdentifier]
    $self = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $writers = @($self.Value, 'S-1-5-18', 'S-1-5-32-544')
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($id in $writers) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sidType::new($id), 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        $sidType::new('S-1-5-32-545'), 'ReadAndExecute', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
    $store = Join-Path $Root 'releases'
    foreach ($path in @($Root, $store)) {
        if ($Create) { [IO.Directory]::CreateDirectory($path, $acl) | Out-Null }
        $item = Get-Item -LiteralPath $path -ErrorAction Stop
        $actual = $item.GetAccessControl()
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $actual.GetOwner($sidType).Value -notin $writers) {
            throw "Untrusted release directory: $path"
        }
        foreach ($rule in $actual.GetAccessRules($true, $true, $sidType)) {
            if ($rule.AccessControlType -ne 'Allow' -or $rule.IdentityReference.Value -in $writers) { continue }
            # On a legacy root, permission to create new names is safe if an
            # existing protected releases directory cannot be replaced.
            $rights = $rule.FileSystemRights
            if ($path -eq $Root -and ($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly)) { continue }
            $unsafe = [Security.AccessControl.FileSystemRights]'Delete,DeleteSubdirectoriesAndFiles,ChangePermissions,TakeOwnership'
            if ($path -eq $store) { $unsafe = $unsafe -bor [Security.AccessControl.FileSystemRights]::Write }
            if ($rights -band $unsafe) { throw "Writable release directory: $path" }
        }
        if ($path -eq $store -and -not $actual.AreAccessRulesProtected) { throw 'Unprotected release store' }
    }
    return $store
}

function Publish-Release([string]$Store, [string]$Id) {
    $marker = Join-Path $Store 'active-release'
    $temp = Join-Path $Store ($Id + '.active.tmp')
    [IO.File]::WriteAllText($temp, $Id)
    try {
        if ([IO.File]::Exists($marker)) {
            # Use the native three-argument overload with a true null backup path.
            [IO.File]::Replace($temp, $marker, [System.Management.Automation.Language.NullString]::Value)
        } else {
            [IO.File]::Move($temp, $marker)
        }
    } finally {
        if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) }
    }
}
