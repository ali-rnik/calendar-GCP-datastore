'use strict';
window.addEventListener('load', function () {
	document.getElementById('sign-out').onclick = function() {
		firebase.auth().signOut();
		window.location.replace('/');

	};

	var uiConfig = {
		signInSuccessUrl: '/',
		signInOptions: [
			firebase.auth.EmailAuthProvider.PROVIDER_ID
		]
	};
	firebase.auth().onAuthStateChanged(function(user) {
		if(user) {
			document.getElementById('sign-out').hidden = false;
			document.getElementById('user-info').hidden = false;
			document.getElementById('popup-firebase').hidden = true;
			user.getIdToken().then(function(token) {
				document.cookie = "token=" + token + ";path=/";
			});
		} else {
			var ui = new firebaseui.auth.AuthUI(firebase.auth());
			ui.start('#firebase-auth-container', uiConfig);
			document.getElementById('sign-out').hidden = true;
			document.getElementById('user-info').hidden = true;
			document.getElementById('popup-firebase').hidden = false;

			document.cookie = "token=;path=/";
		}
	}, function(error) {
		console.log(error);
		alert('Unable to log in: ' + error);
	});
});

function makeVis() {
	document.getElementById("firebase-auth-container").hidden = false;
	document.getElementById("popup-firebase").hidden = true;
}

function snackbar() {
	var x = document.getElementById("snackbar");
	x.className = "show";
	setTimeout(function(){ x.className = x.className.replace("show", ""); }, 3000);
}


