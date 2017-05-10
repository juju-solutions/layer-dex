
def convert_dict_keys(haystack):
    ''' Convert dash characters in a dictionary to underscores for jinja2
    templating logic. This is a quality of life conversion for engineering
    purposes while keeping the quality of life for users high. '''
    new_haystack = {}
    for needle in haystack.keys():
        new_needle = needle.replace('-', '_')
        new_haystack[new_needle] = haystack[needle]

    return new_haystack
