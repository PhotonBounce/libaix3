<?php
header('Content-Type: text/plain');
$python311 = shell_exec('/opt/alt/python311/bin/python3 --version 2>&1');
echo "Python 3.11: " . ($python311 ?: "FAILED") . "\n";
$python310 = shell_exec('/opt/alt/python310/bin/python3 --version 2>&1');
echo "Python 3.10: " . ($python310 ?: "FAILED") . "\n";
?>
