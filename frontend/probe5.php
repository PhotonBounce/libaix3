<?php
header('Content-Type: text/plain');
$passenger = shell_exec('which passenger 2>&1');
echo "Passenger: " . ($passenger ?: "NOT FOUND") . "\n";
$passenger_status = shell_exec('passenger --version 2>&1 | head -1');
echo "Passenger version: " . ($passenger_status ?: "NOT AVAILABLE") . "\n";
echo "Document root: " . $_SERVER['DOCUMENT_ROOT'] . "\n";
?>
