$(function(){
    $('input').click(function(){
        var id = $(this).attr("id");
        $.ajax({
            url: '/pochipochi',
            data: {"name": id},
            type: 'POST',
            success: function(response){
                console.log(response);
            },
            error: function(error){
                console.log(error);
            }
        });
    });
});

