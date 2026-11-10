$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Получаем текущую дату
$today = Get-Date

$folderName = $today.ToString("ddMMyy")

# Указываем базовый каталог
$baseDirectory = "E:\GitlabProjects"

# Объединяем пути
$currentDayDirectory = Join-Path -Path $baseDirectory -ChildPath $folderName

# Проверяем, существует ли каталог, и создаем его, если нет
if (-not (Test-Path $currentDayDirectory)) {
    New-Item -ItemType Directory -Path $currentDayDirectory -Force
    Write-Host "Создан новый каталог для сегодняшнего дня: $currentDayDirectory" -ForegroundColor Green
}

# Устанавливаем текущий каталог
Set-Location -Path $currentDayDirectory
Write-Host "Текущий рабочий каталог установлен на: $currentDayDirectory" -ForegroundColor Cyan

# Проверяем, запущен ли уже скрипт WeatherClock.bat
# Этот метод ищет любой процесс, в командной строке которого упоминается "WeatherClock.bat".
$process = Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%WeatherClock.bat%'"
# Если процесс не найден, запускаем скрипт
if (-not $process) {
 Write-Host "Скрипт E:\WeatherClock\WeatherClock.bat не запущен. Запускаем..." -ForegroundColor Yellow
 Start-Process -FilePath "E:\WeatherClock\WeatherClock.bat"
 } else {
Write-Host "Скрипт E:\WeatherClock\WeatherClock.bat уже запущен." -ForegroundColor Cyan
}
# Import the Chocolatey Profile that contains the necessary code to enable
# tab-completions to function for `choco`.
# Be aware that if you are missing these lines from your profile, tab completion
# for `choco` will not function.
# See https://ch0.co/tab-completion for details.
$ChocolateyProfile = "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1"
if (Test-Path($ChocolateyProfile)) {
  Import-Module "$ChocolateyProfile"
}
