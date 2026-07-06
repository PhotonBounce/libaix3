<?php
// Deployment script for OpsBrief backend
header('Content-Type: text/plain');
set_time_limit(300);

$python = '/opt/alt/python311/bin/python3';
$app_dir = '/home/photonb/public_html/opsbrief/api';
$venv_dir = $app_dir . '/venv';

echo "=== OpsBrief Backend Deployment ===\n\n";

// 1. Create app directory
echo "1. Creating app directory...\n";
if (!is_dir($app_dir)) {
    mkdir($app_dir, 0755, true);
    echo "   Created: $app_dir\n";
} else {
    echo "   Already exists: $app_dir\n";
}

// 2. Create virtual environment
echo "\n2. Creating virtual environment...\n";
if (!is_dir($venv_dir)) {
    $cmd = "$python -m venv $venv_dir 2>&1";
    $out = shell_exec($cmd);
    echo "   $out\n";
} else {
    echo "   Venv already exists\n";
}

// 3. Install pip and upgrade
echo "\n3. Upgrading pip...\n";
$pip = "$venv_dir/bin/pip";
$out = shell_exec("$pip install --upgrade pip setuptools wheel 2>&1");
echo "   " . substr($out, 0, 500) . "\n";

// 4. Install requirements
echo "\n4. Installing requirements...\n";
$req_file = $app_dir . '/requirements.txt';
if (file_exists($req_file)) {
    $out = shell_exec("$pip install -r $req_file 2>&1");
    echo "   " . substr($out, 0, 1000) . "\n";
} else {
    echo "   requirements.txt not found at $req_file\n";
}

echo "\n=== Deployment Complete ===\n";
?>
