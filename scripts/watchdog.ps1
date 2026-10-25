$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$python=Join-Path $projectRoot '.venv/Scripts/python.exe'
while($true){
  try{
    $serviceFile=Join-Path $projectRoot 'data/service.json'
    if(Test-Path -LiteralPath $serviceFile){
      $service=Get-Content -Raw -LiteralPath $serviceFile|ConvertFrom-Json
      $url='http://127.0.0.1:'+ $service.port + '/api/project'
      $healthy=$false
      try{$response=Invoke-RestMethod -Uri $url -TimeoutSec 3;$healthy=$null -ne $response.workspace_id}catch{}
      if(-not $healthy){
        $args=@('"'+(Join-Path $PSScriptRoot 'bootstrap.py')+'"','--port',([string]$service.port))
        Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory $projectRoot -WindowStyle Hidden -Wait
      }
    }
  }catch{}
  Start-Sleep -Seconds 30
}
