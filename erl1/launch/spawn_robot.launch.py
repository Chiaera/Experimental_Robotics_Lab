import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, Command
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():
    pkg_erl1= get_package_share_directory('erl1')
    gazebo_models_path, ignore_last_dir = os.path.split(pkg_erl1)
    
    # lets Gazebo find package://erl1/... (e.g. the meshes)
    gz_path = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    os.environ["GZ_SIM_RESOURCE_PATH"] = gz_path + os.pathsep + gazebo_models_path

    rviz_launch_arg = DeclareLaunchArgument(
        'rviz', default_value='true',
        description='Open RViz.'
    )

    world_arg = DeclareLaunchArgument(
        'world', default_value= 'gazebo_world.sdf',
        description='Name of the Gazebo world file to load'
    )

    model_arg = DeclareLaunchArgument(
        'erl1', default_value='erl1.xacro',
        description='Name of the URDF description to load'
    )

    # Define the path to your URDF or Xacro file
    urdf_file_path = PathJoinSubstitution([
        pkg_erl1, 
        "urdf",
        LaunchConfiguration('erl1') # Replace with your URDF or Xacro file
    ])

    world_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
        os.path.join(pkg_erl1, 'launch', 'gazebo_world.launch.py'),
        ),
        launch_arguments={
            'world': LaunchConfiguration('world'),  
        }.items()
    )

    # Launch rviz
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', os.path.join(pkg_erl1, 'rviz', 'urdf.rviz')],
        condition=IfCondition(LaunchConfiguration('rviz')),
        parameters=[
            {'use_sim_time': True},
        ]
    )

    # Spawn the URDF model using the `/world/<world_name>/create` service
    spawn_urdf_node = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-name", "erl1",
            "-topic", "robot_description",
            "-x", "0.0", "-y", "0.0", "-z", "0.5", "-Y", "0.0" # Initial spawn position
        ],
        output="screen",
        parameters=[
            {'use_sim_time': True},
        ]
    )

    # Robot state publiher
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[
            {'robot_description': ParameterValue(Command(['xacro ', urdf_file_path]), value_type=str),
            'use_sim_time': True},
        ],
        remappings=[
            ('/tf', 'tf'),
            ('/tf_static', 'tf_static')
        ]
    )

    joint_state_publisher_gui_node = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui'
    )

    # Gazebo bridge for the camera
    gz_image_bridge_node = Node(
        package="ros_gz_image",
        executable="image_bridge",
        arguments=[
            "/camera/image",
        ],
        output="screen",
        parameters=[
            {'use_sim_time': True,
             'camera.image.compressed.jpeg_quality': 75},
        ],
    )

    # GAZEVO BRIDGE: Node to bridge messages like /cmd_vel and /odom
    gz_bridge_node = Node (
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments= [
            "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
            "/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model",
            #"/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
            "/camera_joint/cmd_pos@std_msgs/msg/Float64]gz.msgs.Double",
            "/imu@sensor_msgs/msg/Imu[gz.msgs.IMU",
        ],
        output="screen",
        parameters=[
            {'use_sim_time': True},
        ]
    )

    # EKF 
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[
            os.path.join(pkg_erl1, 'config', 'ekf.yaml'),
            {'use_sim_time': True},
        ]
    )

    launchDescriptionObject = LaunchDescription()

    launchDescriptionObject.add_action(rviz_launch_arg)
    launchDescriptionObject.add_action(world_arg)
    launchDescriptionObject.add_action(model_arg)
    launchDescriptionObject.add_action(world_launch)
    launchDescriptionObject.add_action(rviz_node)
    launchDescriptionObject.add_action(spawn_urdf_node)
    launchDescriptionObject.add_action(robot_state_publisher_node)
    launchDescriptionObject.add_action(joint_state_publisher_gui_node)
    launchDescriptionObject.add_action(gz_bridge_node)
    launchDescriptionObject.add_action(gz_image_bridge_node)
    launchDescriptionObject.add_action(ekf_node)

    return launchDescriptionObject



# MEMO TERMINAL:
#   ros2 topic list: all active channels
# 
#   ros2 topic echo /channel_name: "listen" to the topic
# 
#   ros2 topic info /channel_name: verify the type of message associated and the node connected to it 


# TEST:
# 1- TIme
#       gz topic -e -t /clock
#       If Gazebo is at 'play' it should print the seconds number
#
# 2 - Gazebo-Bridge
#       gz topic -e -t /cmd_vel
#       After ros2 run teleop_twist_keyboard teleop_twist_keyboard
#           If the command is pressed, it should print the vel number
#
# 3 - Physics
#       gz topic -e -t /odom
#       It should update the odometry

# CAMERA ROTATION
# ros2 topic pub --once /camera_joint/cmd_pos std_msgs/msg/Float64 "{data: 1.0}"
#
# to see the graphic interface: ros2 run rqt_image_view rqt_image_view
# (selecting from menu camera topic [camera/image])
# to set paramethers: ros2 run rqt_reconfigure rqt_reconfigure

# IMU
# to vizualize IMU in Rviz: sudo apt install ros-jazzy-rviz-imu-plugin

# EKF
# necessary the package: sudo apt install ros-jazzy-robot-localization