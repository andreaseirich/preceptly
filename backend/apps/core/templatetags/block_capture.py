from django import template

register = template.Library()


class CaptureAsNode(template.Node):
    def __init__(self, nodelist, var_name):
        self.nodelist = nodelist
        self.var_name = var_name

    def render(self, context):
        context[self.var_name] = self.nodelist.render(context)
        return ""


@register.tag
def captureas(parser, token):
    try:
        _, _, var_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            "'captureas' requires syntax: {% captureas as varname %}"
        )
    nodelist = parser.parse(("endcaptureas",))
    parser.delete_first_token()
    return CaptureAsNode(nodelist, var_name)
