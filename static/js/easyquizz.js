var socket = null;

var showTimeStamp = true;

var logBox = null;
var messageBox = null;



var user_id = null;
var team = null;

if (!Date.now) {
    Date.now = function() { return new Date().getTime(); }
}





function send(message) {
	if (!socket) {
		addToLog('Not connected');
		return;
	}

	socket.send(JSON.stringify({
  from: message,
  when:Date.now()/1000
}));
}


function addTeam()
{
	if ($("#team_entry").val() != "")
	{
		var new_team_name = $("#team_entry").val();
		var myusername = $("#username").val();
		$.ajax({
		  type: "get",
		  url: "game",
		  data: {user_name : user_name, team:team, req_type:"register_user"},
		  cache: false,
		  success: function(data){
		    alert(data);
		  	user_id = data["id"];
		    alert(user_id);
		  }
		});
	}
}

function init() 
{
  
	var scheme = window.location.protocol == 'https:' ? 'wss://' : 'ws://';
	var defaultAddress = scheme + window.location.host + '/buzz';
	logBox = document.getElementById('log_window');
	// alert(logBox.innerHTML);
	messageBox = document.getElementById('message');

	if (!('WebSocket' in window)) {
		addToLog('WebSocket is not available');
	}
	
}

function addToLog(log) {
  // alert("send");
  logBox.innerHTML = log + '<br/>' + logBox.innerHTML;
  // Large enough to keep showing the latest message.
  //logBox.scrollTop = 1000000;
}

function connect() {
	var scheme = window.location.protocol == 'https:' ? 'wss://' : 'ws://';
	var defaultAddress = scheme + window.location.host + ':80/buzz';
	var url = defaultAddress+'?user='+user_name; 			//addressBox.value;
	addToLog("Connecting to: "+url);

	if ('WebSocket' in window) {
		socket = new WebSocket(url);
	} else {
		return;
	}

	socket.onopen = function () {
		var extraInfo = [];
		if (('protocol' in socket) && socket.protocol) {
			extraInfo.push('protocol = ' + socket.protocol);
		}
		if (('extensions' in socket) && socket.extensions) {
			extraInfo.push('extensions = ' + socket.extensions);
		}

		var logMessage = 'Opened';
		if (extraInfo.length > 0) {
			logMessage += ' (' + extraInfo.join(', ') + ')';
		}
		addToLog(logMessage);
	};
	socket.onmessage = function (event) {
		var obj = JSON.parse(event.data);
		addToLog('< ' + (Date.now()/1000 - obj.when )+' ' +obj.from);
	};
	socket.onerror = function () {
		addToLog('Error');
	};
	socket.onclose = function (event) {
		var logMessage = 'Closed (';
		if ((arguments.length == 1) && ('CloseEvent' in window) &&
		(event instanceof CloseEvent)) {
		logMessage += 'wasClean = ' + event.wasClean;
		// code and reason are present only for
		// draft-ietf-hybi-thewebsocketprotocol-06 and later
		if ('code' in event) {
		logMessage += ', code = ' + event.code;
		}
		if ('reason' in event) {
		logMessage += ', reason = ' + event.reason;
		}
		} else {
		logMessage += 'CloseEvent is not available';
		}
		addToLog(logMessage + ')');
	};
}


function validateSurname()
{
	if ($("#surname").val() != "" && $("team").val() != "")
	{
		user_name = $("#surname").val();
		team = $("#team :selected").text();
		$.ajax({
		  type: "get",
		  url: "game",
		  data: {user_name : user_name, team:team, req_type:"register_user"},
		  cache: false,
		  success: function(data){
		    alert(data);
		  	user_id = data["id"];
		    alert(user_id);
		  }
		});
	}
}


function closeSocket() {
  if (!socket) {
    addToLog('Not connected');
    return;
  }

    socket.close();
}

function buzz()
{
	send(user_name);
}

$(function(){

	init();
	connect();	
	
});