

var can_send=true;
var need_reconnect = false;
function connect_screen() 
{

	if (!('WebSocket' in window)) 
	{
		addToLog('WebSocket is not available');
	}

	var scheme = window.location.protocol == 'https:' ? 'wss://' : 'ws://';
	var defaultAddress = scheme + window.location.host + ':80/screenws';
	var url = defaultAddress; 			//addressBox.value;
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
		if (obj.type=='info')
		{
			addToLog(obj.msg);
		}
		else if (obj.type='update_html')
		{
			update_html(obj.data);
		}
	};
	socket.onerror = function () {
		addToLog('Error');
	};
	socket.onclose = function (event) {
		var logMessage = 'Closed (';
		if ((arguments.length == 1) && ('CloseEvent' in window) &&
				(event instanceof CloseEvent)) 
		{
			logMessage += 'wasClean = ' + event.wasClean;
			// code and reason are present only for
			// draft-ietf-hybi-thewebsocketprotocol-06 and later
			if ('code' in event) 
			{
				if (event.code == 5 && 'reason' in event) 
				{
					$(document.body).empty();
					$(document.body).html("<h1>"+event.reason+"</h1>");
					return;
				}
				logMessage += ', code = ' + event.code;
			}
			if ('reason' in event) 
			{
				logMessage += ', reason = ' + event.reason;
			}
		}
		else 
		{
			logMessage += 'CloseEvent is not available';
		}
		addToLog(logMessage + ')');
		need_reconnect=true;
	};
}

function reconnect()
{
	if (need_reconnect==true)
	{
		connect_screen();
		need_reconnect = false;
		if (!socket) 
		{
			addToLog('Not connected');
			return;
		}
	}
}



$(function() {
	connect_screen();	

});
