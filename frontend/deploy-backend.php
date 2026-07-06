<?php
// Extract and deploy OpsBrief backend
header('Content-Type: text/plain');
set_time_limit(300);

$app_dir = '/home/photonb/public_html/opsbrief/api';
$zip_file = $app_dir . '/backend-deploy.zip';

echo "=== OpsBrief Backend Deployment ===\n\n";

// 1. Create app directory
echo "1. Creating app directory...\n";
if (!is_dir($app_dir)) {
    mkdir($app_dir, 0755, true);
    echo "   Created: $app_dir\n";
} else {
    echo "   Already exists: $app_dir\n";
}

// 2. Extract zip
echo "\n2. Extracting backend zip...\n";
if (file_exists($zip_file)) {
    $zip = new ZipArchive();
    if ($zip->open($zip_file) === TRUE) {
        $zip->extractTo($app_dir);
        $zip->close();
        echo "   Extracted successfully\n";
    } else {
        echo "   FAILED to extract zip\n";
    }
} else {
    echo "   Zip file not found at $zip_file\n";
}

// 3. Create virtual environment
echo "\n3. Creating virtual environment...\n";
$python = '/opt/alt/python311/bin/python3';
$venv_dir = $app_dir . '/venv';
if (!is_dir($venv_dir)) {
    $out = shell_exec("$python -m venv $venv_dir 2>&1");
    echo "   $out\n";
} else {
    echo "   Venv already exists\n";
}

// 4. Upgrade pip
echo "\n4. Upgrading pip...\n";
$pip = "$venv_dir/bin/pip";
$out = shell_exec("$pip install --upgrade pip setuptools wheel 2>&1");
echo "   " . substr($out, 0, 300) . "\n";

// 5. Install requirements
echo "\n5. Installing requirements...\n";
$req_file = $app_dir . '/requirements.txt';
if (file_exists($req_file)) {
    $out = shell_exec("$pip install -r $req_file 2>&1");
    echo "   " . substr($out, -800) . "\n";
} else {
    echo "   requirements.txt not found\n";
}

echo "\n=== Deployment Complete ===\n";
?>
