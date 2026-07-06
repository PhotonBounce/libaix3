<?php
header('Content-Type: text/plain');
set_time_limit(600);
$venv = '/home/photonb/public_html/opsbrief/api/venv';
$pip = "$venv/bin/pip";
$req = '/home/photonb/public_html/opsbrief/api/requirements.txt';

echo "=== Installing requirements ===\n";
$out = shell_exec("$pip install -r $req 2>&1");
echo $out;
echo "\n=== Done ===\n";
?>
