<?php
header('Content-Type: text/plain');
$cgi = '/home/photonb/public_html/opsbrief-api/api.cgi';
echo "Chmod api.cgi...\n";
chmod($cgi, 0755);
echo "Permissions: " . substr(sprintf('%o', fileperms($cgi)), -4) . "\n";
echo "Exists: " . (file_exists($cgi) ? "YES" : "NO") . "\n";
echo "Readable: " . (is_readable($cgi) ? "YES" : "NO") . "\n";
echo "Executable: " . (is_executable($cgi) ? "YES" : "NO") . "\n";
?>
