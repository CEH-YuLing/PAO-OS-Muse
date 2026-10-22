param([Parameter(Mandatory=$true)][string]$TextFile,[Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference='Stop'
$text=Get-Content -LiteralPath $TextFile -Raw -Encoding UTF8
$speaker=New-Object -ComObject SAPI.SpVoice
$stream=New-Object -ComObject SAPI.SpFileStream
try{
  $stream.Open($OutputFile,3,$false)
  $speaker.AudioOutputStream=$stream
  [void]$speaker.Speak($text)
}finally{
  try{$stream.Close()}catch{}
  [Runtime.InteropServices.Marshal]::FinalReleaseComObject($stream)|Out-Null
  [Runtime.InteropServices.Marshal]::FinalReleaseComObject($speaker)|Out-Null
}
