<?php
header('Content-Type: text/plain');
set_time_limit(300);
$venv = '/home/photonb/public_html/opsbrief/api/venv';
$pip = "$venv/bin/pip";

echo "=== Installing missing deps ===\n";
$out = shell_exec("$pip install anyio typing-extensions greenlet MarkupSafe sniffio 2>&1");
echo substr($out, -800);
echo "\n=== Done ===\n";
?>
