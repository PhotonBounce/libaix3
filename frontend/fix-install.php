<?php
header('Content-Type: text/plain');
set_time_limit(600);
$venv = '/home/photonb/public_html/opsbrief/api/venv';
$pip = "$venv/bin/pip";

echo "=== Force reinstall key packages ===\n";
$pkgs = "fastapi==0.115.0 pydantic==2.9.0 pydantic-core==2.23.2 sqlalchemy==2.0.35 starlette==0.38.6";
$out = shell_exec("$pip install --force-reinstall --no-deps $pkgs 2>&1");
echo substr($out, -1000);
echo "\n=== Done ===\n";
?>
