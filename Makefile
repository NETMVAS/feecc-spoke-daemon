test-new-daemon:
	git pull && sudo systemctl restart feecc-spoke-daemon.service && journalctl -u feecc-spoke-daemon.service -f --output cat