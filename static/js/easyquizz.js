

var user_id = null;
var team = null;
var need_reconnect = false;

function connect_player() 
{
	var scheme = window.location.protocol == 'https:' ? 'wss://' : 'ws://';
	var defaultAddress = scheme + window.location.host + '/buzz';

	if (!('WebSocket' in window)) 
	{
		addToLog('WebSocket is not available');
	}

	var scheme = window.location.protocol == 'https:' ? 'wss://' : 'ws://';
	var defaultAddress = scheme + window.location.host + ':80/buzz';
	var url = defaultAddress+'?user='+player; 			//addressBox.value;
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
		if (obj.type=='buzz')
		{
			addToLog('< ' + (obj.when )+' ' +obj.from);
		}
		else if (obj.type=='info')
		{
			addToLog(obj.msg);
		}
		else if (obj.type=='update_html')
		{
			update_html(obj.data);
		}
        else if (obj.type=='buzzerActive')
		{
            activateBuzzer(obj.on);
		}
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
		need_reconnect=true;
	};
}


function validateSurname()
{
	if ($("#surname").val() != "" && $("team").val() != "")
	{
		player = $("#surname").val();
		team = $("#team :selected").text();
		$.ajax({
		  type: "get",
		  url: "game",
		  data: {player : player, team:team, req_type:"register_user"},
		  cache: false,
		  success: function(data){
		    alert(data);
		  	user_id = data["id"];
		    alert(user_id);
		  }
		});
	}
}


function activateBuzzer(trueOrFalse)
{
    if (trueOrFalse == 1)
    {
        console.log("Activate Buzzers.");
        //Change Buzzer style
        $("#buzz").css("color", "white");
        //Display button (could be improved in reactivating button)
        $("#buzz").css("visibility","visible");
    }else{
        console.log("Deactivate Buzzers.");
        //Change Buzzer style
        $("#buzz").css("color", "#8E312F");
        //Hide button (could be improved by inactivating button)
        $("#buzz").css("visibility","hidden");
    }
    
}

function doNothing()
{
    
    addToLog('Buzzer is inactive!');
}

function buzz()
{
	if (need_reconnect==true)
	{
		location.reload();
		return;
		connect_player();
		need_reconnect = false;
		if (!socket) 
		{
			addToLog('Not connected');
			return;
		}
	}

  	socket.send(JSON.stringify({
  		type :'buzz',
  		from : player,
  		when : Date.now()
}));
}

$(function(){
	connect_player();	
});