<#
.SYNOPSIS
Call the local Author Email Extractor API with a single PDF path.

.DESCRIPTION
Sends the given PDF path to POST /extract-author-emails, parses structured_email_string when present,
and prints a short summary by default.

.PARAMETER PdfPath
Absolute PDF path, for example C:/path/to/file.pdf.

.PARAMETER BaseUrl
API base URL. Defaults to http://127.0.0.1:8000.

.PARAMETER ShowFullResponse
Print the full API response after the summary.

.EXAMPLE
.\call_api.ps1 "C:/path/to/file.pdf"

.EXAMPLE
.\call_api.ps1 "C:/path/to/file.pdf" -BaseUrl "http://127.0.0.1:8767"

.EXAMPLE
.\call_api.ps1 "C:/path/to/file.pdf" -ShowFullResponse
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$PdfPath,

    [Parameter()]
    [string]$BaseUrl = "http://127.0.0.1:8000",

    [Parameter()]
    [switch]$ShowFullResponse
)

$ErrorActionPreference = "Stop"

function Convert-StructuredPayload {
    param(
        [Parameter()]
        [object]$ResponseObject
    )

    if (-not $ResponseObject) {
        return $null
    }

    $raw = $ResponseObject.structured_email_string
    if ([string]::IsNullOrWhiteSpace([string]$raw)) {
        return $null
    }

    try {
        return ($raw | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

function Read-ErrorBody {
    param(
        [Parameter(Mandatory = $true)]
        [System.Management.Automation.ErrorRecord]$ErrorRecord
    )

    if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
        return $ErrorRecord.ErrorDetails.Message
    }

    $response = $ErrorRecord.Exception.Response
    if (-not $response) {
        return $null
    }

    try {
        $stream = $response.GetResponseStream()
        if (-not $stream) {
            return $null
        }
        $reader = New-Object System.IO.StreamReader($stream)
        return $reader.ReadToEnd()
    }
    catch {
        return $null
    }
}

function Show-Summary {
    param(
        [Parameter(Mandatory = $true)]
        [object]$ResponseObject,

        [Parameter()]
        [object]$Payload
    )

    $firstAuthor = $null
    $firstAuthorEmail = $null
    $firstAuthorRegion = $null

    if ($Payload) {
        if ($Payload.first_author) {
            $firstAuthor = $Payload.first_author.author_norm
        }
        $firstAuthorEmail = $Payload.first_author_email
        $firstAuthorRegion = $Payload.first_author_region
    }

    [PSCustomObject]@{
        code = $ResponseObject.code
        message = $ResponseObject.message
        first_author = $firstAuthor
        first_author_email = $firstAuthorEmail
        first_author_region = $firstAuthorRegion
    } | Format-List
}

$endpoint = $BaseUrl.TrimEnd("/") + "/extract-author-emails"
$body = @{ pdf_path = $PdfPath } | ConvertTo-Json -Compress

try {
    $response = Invoke-RestMethod -Uri $endpoint -Method Post -ContentType "application/json" -Body $body
    $payload = Convert-StructuredPayload -ResponseObject $response
    Show-Summary -ResponseObject $response -Payload $payload

    if ($ShowFullResponse) {
        ""
        "Full response:"
        $response | ConvertTo-Json -Depth 20
    }
}
catch {
    $rawErrorBody = Read-ErrorBody -ErrorRecord $_
    $parsedError = $null
    if ($rawErrorBody) {
        try {
            $parsedError = $rawErrorBody | ConvertFrom-Json
        }
        catch {
            $parsedError = $null
        }
    }

    if ($parsedError) {
        $payload = Convert-StructuredPayload -ResponseObject $parsedError
        Show-Summary -ResponseObject $parsedError -Payload $payload
        if ($ShowFullResponse) {
            ""
            "Full response:"
            $parsedError | ConvertTo-Json -Depth 20
        }
        exit 1
    }

    Write-Host "Request failed." -ForegroundColor Red
    Write-Host ("Endpoint: " + $endpoint)
    Write-Host ("Reason: " + $_.Exception.Message)
    if ($rawErrorBody) {
        Write-Host ""
        Write-Host "Raw error response:"
        Write-Host $rawErrorBody
    }
    exit 1
}
