unique_id = 0

class Base(object):
    def _make_unique_id(self):
	global unique_id
	unique_id += 1
	return unique_id
