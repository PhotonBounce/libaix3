<?php
header('Content-Type: text/plain');
$venv = '/home/photonb/public_html/opsbrief/api/venv';
$python = "$venv/bin/python3";

// Check if key packages are installed
$packages = ['fastapi', 'sqlalchemy', 'pydantic', 'jwt', 'bcrypt', 'a2wsgi'];
foreach ($packages as $pkg) {
    $out = shell_exec("$python -c \"import $pkg; print('$pkg OK')\" 2>&1");
    echo trim($out) . "\n";
}

// Check backend files
$app_dir = '/home/photonb/public_html/opsbrief/api';
echo "\nBackend files:\n";
foreach (['passenger_wsgi.py', 'requirements.txt'] as $f) {
    $path = "$app_dir/$f";
    echo "$f: " . (file_exists($path) ? "EXISTS" : "MISSING") . "\n";
}

// Check opsbrief package
$opsbrief_dir = "$app_dir/opsbrief";
echo "\nOpsBrief package: " . (is_dir($opsbrief_dir) ? "EXISTS" : "MISSING") . "\n";
if (is_dir($opsbrief_dir)) {
    $files = scandir($opsbrief_dir);
    echo "Files: " . implode(", ", array_diff($files, ['.', '..'])) . "\n";
}
?>
