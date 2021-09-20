import numpy as np
import pandas as pd
import scipy.stats
import copy


def euclidean_distance(mov_data, joint1, joint2):
    """Calculate the euclidean distance between the 2 given joints for all the frames of the grasping movement.

    Args:
        mov_data (pd.DataFrame): A pd.DataFrame containing the skeletal data of the grasping movement and of 9 frames before the beginning of the movement.
        joint1 (str): The name of the first joint.
        joint2 (str): The name of the second joint.

    Returns:
        dist (np.ndarray: An (n,)-dimensional array containg the euclidean distances between the given joint for the n-frames of the grasping movement.
    """
    WINDOW = 10

    x1 = mov_data[f"{joint1}.x"].iloc[WINDOW:].to_numpy()
    y1 = mov_data[f"{joint1}.y"].iloc[WINDOW:].to_numpy()
    
    x2 = mov_data[f"{joint2}.x"].iloc[WINDOW:].to_numpy()
    y2 = mov_data[f"{joint2}.y"].iloc[WINDOW:].to_numpy()

    return np.sqrt((x2-x1)**2 + (y2-y1)**2)

def neighbour_dist(coords):
    """Calculate the distance between the coordinate of the current frame and the previous frame and the distance between the coordinate of the current frame and the next frame.
       For each frame, return the minimum of these two distances.

    Args:
        coords (np.ndarray): An (n,)-dimensional numpy array containg the coordinates for each frame.

    Returns:
        dist (np.ndarray): An (n,)-dimensional numpy array containing the minimum distance for each of the n frames.
    """
    
    dist = np.abs(coords[1:] - coords[:-1])
    prev_dist = np.r_[dist[0], dist]
    next_dist = np.r_[dist, dist[-1]]
    dist = np.min([prev_dist, next_dist], axis=0)
    return dist

def filter_aperture(aperture, mov_data, joint1, joint2):
    """Find the noisy aperture feature values and replace them with NaN.

    Args:
        aperture (np.ndarray): The aperture feature values of the two given joints for the frames of the movement.
        mov_data (pd.DataFrame): A pd.DataFrame containing the skeletal data of the grasping movement and of 9 frames before the beginning of the movement.
        joint1 (str): The name of the first joint.
        joint2 (str): The name of the second joint.
    """

    WINDOW = 10
    PROB_THRESHOLD = 0.6
    DIST_THRESHOLD = 10

    x1 = mov_data[f"{joint1}.x"].iloc[WINDOW:].to_numpy()
    y1 = mov_data[f"{joint1}.y"].iloc[WINDOW:].to_numpy()
    prob1 = mov_data[f"{joint1}.prob"].iloc[WINDOW:].to_numpy()

    x2 = mov_data[f"{joint2}.x"].iloc[WINDOW:].to_numpy()
    y2 = mov_data[f"{joint2}.y"].iloc[WINDOW:].to_numpy()
    prob2 = mov_data[f"{joint2}.prob"].iloc[WINDOW:].to_numpy()

    invalid_frames = np.logical_not((prob1 > PROB_THRESHOLD) & (prob2 > PROB_THRESHOLD) & \
                                    (neighbour_dist(x1) < DIST_THRESHOLD) & (neighbour_dist(x2) < DIST_THRESHOLD) & \
                                    (neighbour_dist(y1) < DIST_THRESHOLD) & (neighbour_dist(y2) < DIST_THRESHOLD))

    aperture[invalid_frames] = np.nan

def calculate_aperture(mov_data, joint1, joint2):
    """Calculate the aperture feature for the given joints for all the frames of the grasping movement. The noisy aperture values are filtered out.

    Args:
        mov_data (pd.DataFrame): A pd.DataFrame containing the skeletal data of the grasping movement and of 9 frames before the beginning of the movement.
        joint1 (str): The name of the first joint.
        joint2 (str): The name of the second joint.

    Returns:
        aperture (np.ndarray): An (n,)-dimensional numpy array containing the aperture of the given joints for each of the n frames. 
    """
    aperture = euclidean_distance(mov_data, joint1, joint2)
    filter_aperture(aperture, mov_data, joint1, joint2)
    return aperture

def calculate_wrist_stddev(mov_data, axis):
    """ Calculate the standard deviation of the right wrist for the given axis.

    Args:
        mov_data (pd.DataFrame): A pd.DataFrame containing the skeletal data of the grasping movement and of 9 frames before the beginning of the movement.
        axis (str): The axis string is either "x" or "y" and indicates the axis for which the wrist coordinates' dispersion is calculated.

    Returns:
        wrist_std_dev (list): A list with length n, where n is the number of frames of the grasping movement. Each entry of the list corresponds to the standard deviation that is assigned to the last frame
                             of the window as a measure of the wrist's speed in the given axis.
    """

    WINDOW = 10

    coords = mov_data[f"RWrist.{axis}"].to_numpy()
    wrist_std_dev = []
    for f in range(WINDOW, coords.shape[0]):
        m = np.average(coords[f-WINDOW:f])
        frame_std_dev = np.sqrt(np.average((coords[f-WINDOW:f]-m)**2))
        wrist_std_dev.append(frame_std_dev)
    return wrist_std_dev

def calculate_wrist_stddist(mov_data):
    """ Calculate the standard distance of the right wrist for the (x,y)-plane.

    Args:
        mov_data (pd.DataFrame): A pd.DataFrame containing the skeletal data of the grasping movement and of 9 frames before the beginning of the movement.

    Returns:
        wrist_std_dist (list): A list with length n, where n is the number of frames of the grasping movement. Each entry of the list corresponds to the standard distance that is assigned to the last frame
                             of the window as a measure of the wrist's speed in the (x,y)-plane.
    """

    WINDOW = 10

    x_coords = mov_data["RWrist.x"].to_numpy()
    y_coords = mov_data["RWrist.y"].to_numpy()
    wrist_std_dist = []
    for f in range(WINDOW, mov_data.shape[0]):
        mx = np.average(x_coords[f-WINDOW:f])
        my = np.average(y_coords[f-WINDOW:f])
        frame_std_dist = np.sqrt(np.average((x_coords[f-WINDOW:f]-mx)**2 + (y_coords[f-WINDOW:f]-my)**2))
        wrist_std_dist.append(frame_std_dist)
    return wrist_std_dist

def calculate_wrist_axis_speed(mov_data, axis):
    """ Calculate the instantaneous speed of the wrist keypoint for the given axis for each of the frames of the grasping movement.

    Args:
        mov_data (pd.DataFrame): A pd.DataFrame containing the skeletal data of the grasping movement and of 9 frames before the beginning of the movement.
        axis (str): The axis string is either "x" or "y" and indicates the axis for which the wrist coordinates' dispersion is calculated.

    Returns:
        wrist_ax_speed (np.ndarray): A (n,)-dimensional numpy array which for each of the n frames contains the instantaneous speed of the right wrist keypoint for the given axis. 
    """
    
    WINDOW = 10

    curr_coords = mov_data[f"RWrist.{axis}"].iloc[WINDOW:].to_numpy()
    prev_coords = mov_data[f"RWrist.{axis}"].iloc[WINDOW-1:-1].to_numpy()

    curr_time = mov_data["Time"].iloc[WINDOW:].to_numpy()
    prev_time = mov_data["Time"].iloc[WINDOW-1:-1].to_numpy()

    dx = np.abs(curr_coords - prev_coords)
    dt = curr_time - prev_time
    wrist_ax_speed = dx/dt
    return wrist_ax_speed

def calculate_wrist_plane_speed(mov_data):
    """ Calculate the instantaneous speed of the wrist keypoint for the (x,y)-plane for each of the frames of the grasping movement.

    Args:
        mov_data (pd.DataFrame): A pd.DataFrame containing the skeletal data of the grasping movement and of 9 frames before the beginning of the movement.

    Returns:
        wrist_xy_speed (np.ndarray): A (n,)-dimensional numpy array which for each of the n frames contains the instantaneous speed of the right wrist keypoint for the (x,y)-plane. 
    """
    
    WINDOW = 10

    curr_x_coords = mov_data[f"RWrist.x"].iloc[WINDOW:].to_numpy()
    prev_x_coords = mov_data[f"RWrist.x"].iloc[WINDOW-1:-1].to_numpy()

    curr_y_coords = mov_data[f"RWrist.y"].iloc[WINDOW:].to_numpy()
    prev_y_coords = mov_data[f"RWrist.y"].iloc[WINDOW-1:-1].to_numpy()

    curr_time = mov_data["Time"].iloc[WINDOW:].to_numpy()
    prev_time = mov_data["Time"].iloc[WINDOW-1:-1].to_numpy()

    dx = np.sqrt((curr_x_coords-prev_x_coords)**2 + (curr_y_coords-prev_y_coords)**2)
    dt = curr_time - prev_time
    wrist_xy_speed = dx/dt
    return wrist_xy_speed


def calculate_norm_time(mov_data):
    """Calculate the normalized time (movement completion percentage) for each of the frames of the grasping movement based on the absolute time of each frame ("Time" column).

    Args:
        mov_data (pd.DataFrame): A pd.DataFrame containing the skeletal data of the grasping movement and of 9 frames before the beginning of the movement.
    """

    WINDOW = 10

    abs_time = mov_data["Time"].iloc[WINDOW:].to_numpy()
    norm_time = 100.0 * (abs_time - abs_time[0]) / (abs_time[-1] - abs_time[0])
    return norm_time

def mov_feature_engineering(mov_data, feature_set):
    """ Engineer the given kinematic features and the normalized time (movement completion percentage) for each of the frames of the grasping movement.

    Args:
        mov_data (pd.DataFrame): A pd.DataFrame containing the skeletal data of the grasping movement and of 9 frames before the beginning of the movement.
        feature_set (set): A set containing the names of the kinematic features to be engineered.

    Returns:
        feature_df (pd.DataFrame): A pd.DataFrame containing a timestamp and the engineered kinematic features for each of the frames of the graspin movement.
    """

    WINDOW = 10

    feature_dict = dict()
    feature_dict["abs_time"] = mov_data["Time"].iloc[WINDOW:]
    feature_dict["norm_time"] = calculate_norm_time(mov_data)
    if "thumb-index aperture" in feature_set:   feature_dict["thumb-index aperture"] = calculate_aperture(mov_data, "RThumb4FingerTip", "RIndex4FingerTip")
    if "thumb-middle aperture" in feature_set:  feature_dict["thumb-middle aperture"] = calculate_aperture(mov_data, "RThumb4FingerTip", "RMiddle4FingerTip")
    if "index-middle aperture" in feature_set:  feature_dict["index-middle aperture"] = calculate_aperture(mov_data, "RIndex4FingerTip", "RMiddle4FingerTip")
    if "wrist x-coord" in feature_set: feature_dict["wrist x-coord"] = mov_data["RWrist.x"].iloc[WINDOW:]
    if "wrist y-coord" in feature_set: feature_dict["wrist y-coord"] = mov_data["RWrist.y"].iloc[WINDOW:]
    if "wrist x-std_dev" in feature_set: feature_dict["wrist x-std_dev"] = calculate_wrist_stddev(mov_data, "x")
    if "wrist y-std_dev" in feature_set: feature_dict["wrist y-std_dev"] = calculate_wrist_stddev(mov_data, "y")
    if "wrist xy-std_dist" in feature_set: feature_dict["wrist xy-std_dist"] = calculate_wrist_stddist(mov_data)
    if "wrist x-speed" in feature_set: feature_dict["wrist x-speed"] = calculate_wrist_axis_speed(mov_data, "x")
    if "wrist y-speed" in feature_set: feature_dict["wrist-y speed"] = calculate_wrist_axis_speed(mov_data, "y")
    if "wrist xy-speed" in feature_set: feature_dict["wrist-xy speed"] = calculate_wrist_plane_speed(mov_data)

    features_df = pd.DataFrame(feature_dict)
    return features_df

def feature_engineering(data, feature_set):
    """ Engineer the given kinematic features for the grasping phase of all the movements of the dataset. Uupdate the data dictionary by replacing the skeletal data with the engineered kinematic features
        and the absolute time with normalized time.

    Args:
        data (dictionary): A dictionary with the movement filename as the key and a pd.DataFrame containing the corresponding skeletal data of the grasping movement and the skeletal data of 9 frames
                           before the beginning of the movement as the value.
        feature_set (set): A set containing the names of the kinematic features to be engineered.
    """
    for mov_name, mov_data in data.items():
        mov_data = mov_feature_engineering(mov_data, feature_set)
        data[mov_name] = mov_data


def feature_statistics_extraction(data):
    """ For each kinematic feature that was engineered and for each of the 20%, 40%, 60%, 80% and 100% movement completion intervals extract the summary statistics of the kinematic feature values that occured in this
        interval. For each kinematic feature the following summary statistics are calculated:
        - the minimum (min), the maximum (max), the average (mean) and the standard deviation (std) of the kinematic feature values.
        - the absolute time that the maximum (tmax) and the minimum (tmin) of the kinematic feature values occured.
        - the slope of a linear least-squares regression which is calculated based on the absolute time and the kinematic feature values. 
        Finally the number of frames that were captured during this movement completion interval is used as a summary statistic.

        The NaN values are replaced by 0.

    Args:
        data (dict): A dictionary with the movement filename as the key and a pd.DataFrame containing the corresponding kinematic features of the grasping movement and the skeletal data of 9 frames
                     before the beginning of the movement as the value.

    Returns:
        partial_data (dict): A dictionary with a "<movement filename>_<movement completion percentage>" string as key and a 1-dimensional numpy array containing the summary statistics of the enigeered kinematic features for
                             the corresponding movement and movement completion percentage. If F kinematic features were engineered, the numpy arrays have size (1+7*F,).
    """

    partial_data = dict()
    for mov_compl in [20, 40, 60, 80, 100]:
        
        for mov_name, mov_data in data.items():
            partial_mov_data = mov_data[mov_data["norm_time"] <= mov_compl]
            points_no = partial_mov_data.shape[0]

            non_time_data = partial_mov_data[partial_mov_data.columns.difference(['abs_time', 'norm_time'])]
            
            features_min = non_time_data.min(axis=0, skipna=True) 
            features_max = non_time_data.max(axis=0, skipna=True)
            features_mean = non_time_data.mean(axis=0, skipna=True)
            features_std = non_time_data.std(axis=0, ddof=0, skipna=True)

            features_tmax = non_time_data.set_index(partial_mov_data['abs_time']).idxmax(axis=0, skipna=True)
            features_tmin = non_time_data.set_index(partial_mov_data['abs_time']).idxmin(axis=0, skipna=True)
            
            slopes = []
            mask = non_time_data == non_time_data
            for feature in non_time_data.columns:
                feature_mask = mask[feature]
                if feature_mask.sum(axis=0) > 1:
                    t = partial_mov_data["abs_time"][feature_mask]
                    f = non_time_data[feature][feature_mask]
                    slope, _, _, _, _ = scipy.stats.linregress(t,f)
                else:
                    slope = 0
                slopes.append(slope)

            features_stats = np.r_[points_no, features_mean, features_std, features_max, features_min, features_tmax, features_tmin, slopes]
            np.nan_to_num(features_stats, copy=False)

            partial_data[f"{mov_name}_{mov_compl}"] = features_stats

    return partial_data
            