<?php
header('Content-Type: text/plain');
$log_files = [
    '/home/photonb/logs/passenger.log',
    '/home/photonb/public_html/opsbrief-api/passenger.log',
    '/home/photonb/public_html/opsbrief-api/error.log',
    '/tmp/passenger.log',
];
foreach ($log_files as $f) {
    echo "=== $f ===\n";
    if (file_exists($f)) {
        $content = file_get_contents($f);
        echo substr($content, -2000) . "\n\n";
    } else {
        echo "NOT FOUND\n\n";
    }
}
?>
