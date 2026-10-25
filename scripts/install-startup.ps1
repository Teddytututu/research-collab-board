param([switch]$Install,[switch]$Watchdog)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
if(-not $Install){Write-Output 'Optional: run with -Install after choosing startup behavior. Add -Watchdog for background recovery.';exit 0}
$startupFolder=[Environment]::GetFolderPath('Startup')
$startupName='ResearchCollabBoard-'+([System.IO.Path]::GetFileName($projectRoot))+'.lnk'
$shortcutPath=Join-Path $startupFolder $startupName
if(Test-Path -LiteralPath $shortcutPath){throw 'An entry already exists. Review that entry before replacing it.'}
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut($shortcutPath)
if($Watchdog){$link.TargetPath=(Get-Command powershell.exe).Source;$link.Arguments='-NoProfile -WindowStyle Hidden -File "'+(Join-Path $PSScriptRoot 'watchdog.ps1')+'"'}
else{$link.TargetPath=Join-Path $projectRoot '.venv/Scripts/pythonw.exe';$link.Arguments='"'+(Join-Path $PSScriptRoot 'bootstrap.py')+'"'}
$link.WorkingDirectory=$projectRoot;$link.WindowStyle=7;$link.Description='Local research collaboration board';$link.Save()
Write-Output 'Startup entry created for this project.'
