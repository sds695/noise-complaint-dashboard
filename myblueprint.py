from flask import Blueprint

# a random blueprint
myblueprint = Blueprint(name='mycustomblueprint',
                         import_name='blueprint_name', # name of the file
                         static_folder='static', # a folder inside app/myblueprint/static
                         template_folder='templates', # a folder inside app/myblueprint/templates
                         static_url_path='/static', # this is what mycustomblueprint.static will point to, and if the name is admin it will be admin.static, thus colliding with flask-admin
                         url_prefix='/myblueprintprefix', # this will be appended to each view inside your blueprint, i.e. a view '/foo' will get converted into '/myblueprintprefix/foo' in your url mappings
                         subdomain=None,
                         url_defaults=None,
                         root_path=None)

