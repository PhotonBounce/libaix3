<?php
header('Content-Type: text/plain');
echo "Server: " . $_SERVER['SERVER_SOFTWARE'] . "\n";
echo "PHP: " . phpversion() . "\n";
$python = shell_exec('python3 --version 2>&1');
echo "Python3: " . ($python ?: "NOT FOUND") . "\n";
$python2 = shell_exec('python --version 2>&1');
echo "Python: " . ($python2 ?: "NOT FOUND") . "\n";
$pip = shell_exec('pip3 --version 2>&1');
echo "Pip3: " . ($pip ?: "NOT FOUND") . "\n";
$which = shell_exec('which python3 2>&1');
echo "Python3 path: " . ($which ?: "NOT FOUND") . "\n";
?>
