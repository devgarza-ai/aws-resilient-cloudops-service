<#
.SYNOPSIS
Sample one explicitly supplied HTTP endpoint and write neutral elapsed evidence.
.DESCRIPTION
Reusable adaptation of the project observer. No AWS credentials are required.
Existing output files are preserved. Backend hostnames become in-memory aliases.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ $_.IsAbsoluteUri -and $_.Scheme -in @('http', 'https') })]
    [uri]$Url,
    [string]$OutputPath = (Join-Path -Path (Get-Location).Path -ChildPath 'probe-output.csv'),
    [ValidateRange(1, 10000)]
    [int]$MaxSamples = 300,
    [ValidateRange(1, 60)]
    [int]$IntervalSeconds = 2
)

if (Test-Path -LiteralPath $OutputPath) {
    throw 'Output already exists. Choose a new OutputPath to preserve prior evidence.'
}
$outputDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($OutputPath))
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    throw 'The output directory must already exist.'
}

$backendAliases = @{}
$previousProgress = $ProgressPreference
$ProgressPreference = 'SilentlyContinue'
$runWatch = [Diagnostics.Stopwatch]::StartNew()
$firstElapsed = $null

try {
    for ($sample = 1; $sample -le $MaxSamples; $sample++) {
        $startElapsed = $runWatch.Elapsed.TotalSeconds
        if ($null -eq $firstElapsed) { $firstElapsed = $startElapsed }
        $elapsed = [math]::Round($startElapsed - $firstElapsed, 7)
        $status = 0
        $backend = 'unavailable'
        $errorCategory = ''
        $requestWatch = [Diagnostics.Stopwatch]::StartNew()

        try {
            $response = Invoke-WebRequest -Uri $Url.AbsoluteUri -UseBasicParsing -DisableKeepAlive -TimeoutSec 5 -ErrorAction Stop
            $status = [int]$response.StatusCode
            $backend = 'unknown'
            $match = [regex]::Match([string]$response.Content, 'Served by:\s*([^<]+)')
            if ($match.Success) {
                $hostIdentity = $match.Groups[1].Value.Trim()
                if (-not $backendAliases.ContainsKey($hostIdentity)) {
                    $backendAliases[$hostIdentity] = 'backend-{0}' -f ($backendAliases.Count + 1)
                }
                $backend = $backendAliases[$hostIdentity]
            }
            if ($status -ne 200) { $errorCategory = 'http-error' }
        }
        catch {
            if ($null -ne $_.Exception.Response) {
                $status = [int]$_.Exception.Response.StatusCode
                $errorCategory = 'http-error'
            }
            else { $errorCategory = 'transport-error' }
        }

        $requestWatch.Stop()
        [pscustomobject]@{
            Sample = $sample
            ElapsedSeconds = $elapsed.ToString('0.0000000', [Globalization.CultureInfo]::InvariantCulture)
            HttpStatus = $status
            BackendRole = $backend
            RequestDurationMs = $requestWatch.ElapsedMilliseconds
            ErrorCategory = $errorCategory
        } | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Append -Encoding UTF8 -ErrorAction Stop

        Write-Host ('Sample {0}: HTTP {1}, {2}, {3}ms' -f $sample, $status, $backend, $requestWatch.ElapsedMilliseconds)
        if ($sample -lt $MaxSamples) { Start-Sleep -Seconds $IntervalSeconds }
    }
}
finally {
    $runWatch.Stop()
    $ProgressPreference = $previousProgress
    Write-Host ('Evidence file: {0}' -f $OutputPath)
}
