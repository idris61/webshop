// Scroll to Top Button - CC Culinary
frappe.ready(function() {
	// Butonu oluştur
	const scrollBtn = $('<button id="scroll-to-top" title="Yukarı Çık">' +
		'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
		'<polyline points="18 15 12 9 6 15"></polyline>' +
		'</svg>' +
		'</button>');
	
	$('body').append(scrollBtn);
	
	// Scroll durumunda göster/gizle
	$(window).scroll(function() {
		if ($(this).scrollTop() > 300) {
			$('#scroll-to-top').fadeIn();
		} else {
			$('#scroll-to-top').fadeOut();
		}
	});
	
	// Tıklandığında yukarı kaydır
	$('#scroll-to-top').click(function() {
		$('html, body').animate({scrollTop: 0}, 600);
		return false;
	});
});

