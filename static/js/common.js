var socket = null;

var logBox = null;



if (!Date.now) 
{
    Date.now = function() { return new Date().getTime(); }
}


function addToLog(log) 
{
  // alert("send");
  logBox.innerHTML = log + '<br/>' + logBox.innerHTML;
  // Large enough to keep showing the latest message.
  //logBox.scrollTop = 1000000;
}

function update_html(content)
{
	$.each(content, function (k, v) {
		$('#'+k).html(v);
	});

}