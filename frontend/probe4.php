<?php
header('Content-Type: text/plain');
$pip = shell_exec('/opt/alt/python311/bin/pip3 --version 2>&1');
echo "Pip: " . ($pip ?: "FAILED") . "\n";
$venv = shell_exec('/opt/alt/python311/bin/python3 -m venv --help 2>&1 | head -1');
echo "Venv: " . ($venv ?: "FAILED") . "\n";
?>
