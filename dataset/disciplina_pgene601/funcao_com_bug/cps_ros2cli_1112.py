def get_port():
    base_port = 11511
    base_port += int(os.environ.get('ROS_DOMAIN_ID', 0))
    return base_port
