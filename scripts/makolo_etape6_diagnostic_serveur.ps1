param(
    [string]$BaseUrl = 'http://127.0.0.1:9999',
    [int]$Iterations = 5,
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
if ($Iterations -lt 2 -or $Iterations -gt 30) { throw 'Iterations doit etre compris entre 2 et 30.' }
Add-Type -AssemblyName System.Net.Http
$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.AutomaticDecompression = [System.Net.DecompressionMethods]::None
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
$client.DefaultRequestHeaders.TryAddWithoutValidation('Accept-Encoding', 'identity') | Out-Null
$root = $BaseUrl.TrimEnd('/')

function Measure-Discovery([string]$Label, [string]$Path) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $response = $client.GetAsync("$root$Path").GetAwaiter().GetResult()
    $bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
    $sw.Stop()
    $status = [int]$response.StatusCode
    if (-not $response.IsSuccessStatusCode) {
        throw "HTTP $status pour $Label (corps non affiche pour confidentialite)"
    }
    $raw = [System.Text.Encoding]::UTF8.GetString($bytes)
    $parsed = $raw | ConvertFrom-Json
    $data = $parsed.data
    if ($null -eq $data) { throw "Enveloppe data absente: $Label" }
    $spatial = $data.spatial_index
    $countSpatial = if ($null -eq $spatial) { $null } else { $spatial.count }
    $detailAvailable = if ($null -eq $spatial) { $null } else { $spatial.detail_available }
    $spatialRows = if ($null -eq $spatial -or $null -eq $spatial.results) { $null } else { @($spatial.results).Count }
    [PSCustomObject]@{
        Scenario = $Label
        Ms = [Math]::Round($sw.Elapsed.TotalMilliseconds,1)
        Bytes = $bytes.Length
        KB = [Math]::Round($bytes.Length / 1KB,1)
        HTTP = $status
        Total = $data.count
        N1 = @($data.results).Count
        Items = @($data.items).Count
        Index = $countSpatial
        IndexRows = $spatialRows
        Detail = $detailAvailable
        HasNext = $data.has_next
    }
}

try {
    $scenarios = @(
        @{ Label='N1 seul'; Path='/api/v1/discovery/items/?page=1&page_size=24' },
        @{ Label='N1 + carte'; Path='/api/v1/discovery/items/?page=1&page_size=24&include_spatial_index=1' },
        @{ Label='Page 2'; Path='/api/v1/discovery/items/?page=2&page_size=24' }
    )
    Write-Host 'Echauffement (non comptabilise)...'
    foreach ($s in $scenarios) { $null = Measure-Discovery $s.Label $s.Path }
    $samples = @()
    for ($i=1; $i -le $Iterations; $i++) {
        foreach ($s in $scenarios) {
            $sample = Measure-Discovery $s.Label $s.Path
            $samples += $sample
            Write-Host ("Passage {0}/{1} : {2} | {3} ms | {4} Ko" -f $i,$Iterations,$sample.Scenario,$sample.Ms,$sample.KB)
        }
    }
    Write-Host "`nSynthese (mediane des temps, taille moyenne):"
    $summary = foreach ($s in $scenarios) {
        $group = @($samples | Where-Object { $_.Scenario -eq $s.Label })
        $times = @($group | ForEach-Object { $_.Ms } | Sort-Object)
        $middle = [int][Math]::Floor($times.Count / 2)
        $median = if ($times.Count % 2 -eq 1) { $times[$middle] } else { ($times[$middle-1]+$times[$middle])/2 }
        [PSCustomObject]@{
            Scenario=$s.Label
            MedianMs=[Math]::Round($median,1)
            MinMs=($times | Measure-Object -Minimum).Minimum
            MaxMs=($times | Measure-Object -Maximum).Maximum
            MeanKB=[Math]::Round(($group | Measure-Object -Property KB -Average).Average,1)
            N1=$group[-1].N1
            Items=$group[-1].Items
            Total=$group[-1].Total
            Index=$group[-1].Index
            IndexRows=$group[-1].IndexRows
            Detail=$group[-1].Detail
        }
    }
    $summary | Format-Table -AutoSize
    $first = $summary | Where-Object { $_.Scenario -eq 'N1 seul' }
    $spatial = $summary | Where-Object { $_.Scenario -eq 'N1 + carte' }
    $deltaKB = $spatial.MeanKB-$first.MeanKB
    $deltaMs = $spatial.MedianMs-$first.MedianMs
    Write-Host ("Surcout observe de l'index : {0:N1} Ko et {1:N1} ms (mediane)" -f $deltaKB,$deltaMs)
    if ($spatial.Index -ne $spatial.IndexRows) { Write-Warning 'Le count spatial differe du nombre de lignes indexees.' }
    if ($spatial.N1 -ne $spatial.Items) { Write-Warning 'results/items ont des longueurs differentes.' }
    if ($spatial.Index -eq $null -or $spatial.Detail -ne $true) { Write-Warning 'Index spatial enrichi non disponible dans la reponse.' }
    if (($summary | Where-Object { $_.Scenario -eq 'Page 2' }).Index -ne $null) { Write-Warning 'Index spatial inattendu en page 2.' }
    Write-Host 'Aucune reponse JSON, identite, coordonnee ni credential n''a ete imprime.'
} finally {
    $client.Dispose()
    $handler.Dispose()
}
