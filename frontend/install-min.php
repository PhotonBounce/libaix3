<?php
header('Content-Type: text/plain');
set_time_limit(600);
$venv = '/home/photonb/public_html/opsbrief/api/venv';
$pip = "$venv/bin/pip";
$req = '/home/photonb/public_html/opsbrief/api/requirements-min.txt';
echo "=== Installing core packages ===
";
$out = shell_exec("$pip install -r $req 2>&1");
echo substr($out, -1500);
echo "
=== Done ===
";
?>