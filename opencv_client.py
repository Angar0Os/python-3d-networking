import harfang as hg
import time
import numpy as np
import cv2
import ctypes
import math

def InitRenderToTexture(res, frame_buffer_name = "FrameBuffer", pipeline_texture_name = "tex_rb", texture_name = "tex_color_ref", res_x = 512, res_y = 512):
	frame_buffer = hg.CreateFrameBuffer(res_x, res_y, hg.TF_RGBA8, hg.TF_D24, 4, frame_buffer_name)
	color = hg.GetColorTexture(frame_buffer)

	tex_color_ref = res.AddTexture(pipeline_texture_name, color)
	tex_readback = hg.CreateTexture(res_x, res_y, texture_name, hg.TF_ReadBack | hg.TF_BlitDestination, hg.TF_RGBA8)

	picture = hg.Picture(res_x, res_y, hg.PF_RGBA32)

	return frame_buffer, color, tex_color_ref, tex_readback, picture

def GetOpenCvImageFromPicture(picture):
	picture_width, picture_height = picture.GetWidth(), picture.GetHeight()
	picture_data = picture.GetData()
	bytes_per_pixels = 4
	data_size = picture_width * picture_height * bytes_per_pixels
	buffer = (ctypes.c_char * data_size).from_address(picture_data)
	raw_data = bytes(buffer)
	np_array = np.frombuffer(raw_data, dtype=np.uint8)
	image_rgba = np_array.reshape((picture_height, picture_width, bytes_per_pixels))
	image_bgr = cv2.cvtColor(image_rgba, cv2.COLOR_BGR2RGB)

	return image_bgr

def ProcessInputs(input_value, pos, rot, front, dt, trs):
    match input_value:
        case "UP":
            trs.SetPos(pos + front * (hg.time_to_sec_f(dt) * 10))
            return
        case "DOWN":
            trs.SetPos(pos - front * (hg.time_to_sec_f(dt) * 10))
            return
        case "RIGHT":
            trs.SetRot(hg.Vec3(rot.x, rot.y + (hg.time_to_sec_f(dt)) * 10, rot.z))
            return
        case "LEFT":
            trs.SetRot(hg.Vec3(rot.x, rot.y - (hg.time_to_sec_f(dt)) * 10, rot.z))
            return
        case _:
            return "Must be a valid input"

def DetectQrCode(image):
    qrCodeDetector = cv2.QRCodeDetector()
    decodedText, points, _ = qrCodeDetector.detectAndDecode(image)

    if points is not None:
        points = points[0]
        print(f"QR Code détecté : {decodedText}")

        points_int = points.astype(int)
        for i in range(len(points_int)):
            start_point = tuple(points_int[i])
            end_point = tuple(points_int[(i + 1) % len(points_int)])
            cv2.line(image, start_point, end_point, (255, 0, 0), 2)

        if decodedText:
            cv2.putText(image, decodedText, (points_int[0][0], points_int[0][1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            return "Moving", decodedText
        return "Lost", None
    return "Lost", None

def GoTo(player_position, rot, front, image, trs, dt, lost_timer):
	player_state, qr_code_datas = DetectQrCode(image)

	if player_state == "Lost":
		if lost_timer == 0:
			lost_timer = time.time()

		elapsed_time = time.time() - lost_timer

		if elapsed_time < 10:
			ProcessInputs("RIGHT", player_position, rot, front, dt, trs)
		elif 10 <= elapsed_time < 15:
			ProcessInputs("UP", player_position, rot, front, dt, trs)
		else:
			lost_timer = 0

	if player_state == "Moving":
		ProcessInputs("UP", player_position, rot, front, dt, trs)
		lost_timer = 0

	return lost_timer

def main():
	goToTarget = False
	id_target_positions = 0

	hg.InputInit()
	hg.WindowSystemInit()

	res_x, res_y = 1280, 720

	win = hg.NewWindow('3D Server - Client Scene', res_x, res_y)
	hg.RenderInit(win)

	pipeline = hg.CreateForwardPipeline()
	res = hg.PipelineResources()

	hg.AddAssetsFolder("server_client_demo_compiled")
	hg.ImGuiInit(10, hg.LoadProgramFromAssets('core/shader/imgui'), hg.LoadProgramFromAssets('core/shader/imgui_image'))

	vtx_layout = hg.VertexLayout()
	vtx_layout.Begin()
	vtx_layout.Add(hg.A_Position, 3, hg.AT_Float)
	vtx_layout.End()

	scene = hg.Scene()
	hg.LoadSceneFromAssets("level_1_full.scn", scene, res, hg.GetForwardPipelineInfo())

	pipeline_aaa_config = hg.ForwardPipelineAAAConfig()
	pipeline_aaa = hg.CreateForwardPipelineAAAFromAssets("core", pipeline_aaa_config, hg.BR_Equal, hg.BR_Equal)
	pipeline_aaa_config.sample_count = 1
	pipeline_aaa_config.motion_blur = 0

	keyboard = hg.Keyboard()
	mouse = hg.Mouse()

	frame = 0
	state = "none"

	cam = scene.GetNode("Camera")
	trs = scene.GetNode("red_player")
	z_near = cam.GetCamera().GetZNear()
	z_far = cam.GetCamera().GetZFar()
	fov = cam.GetCamera().GetFov()

	camera_world_transform = hg.TransformationMat4(hg.Vec3(0,1,0), hg.Vec3(0,0,0))
	camera_robot = hg.CreateCamera(scene, camera_world_transform, z_near, z_far, fov)
	camera_robot.GetTransform().SetParent(trs)

	frame_buffer, color, tex_color_ref, tex_readback, picture = InitRenderToTexture(res)
	lost_timer = 0

	while not hg.ReadKeyboard().Key(hg.K_Escape) and hg.IsWindowOpen(win):
		render_was_reset, res_x, res_y = hg.RenderResetToWindow(win, res_x, res_y, hg.RF_VSync)
		keyboard.Update()
		mouse.Update()
		dt = hg.TickClock()

		vid = 0

		min_node_pos = scene.GetNode('area_min').GetTransform().GetPos()
		max_node_pos = scene.GetNode('area_max').GetTransform().GetPos()
		min_x = min_node_pos.x
		min_z = min_node_pos.z
		max_x = max_node_pos.x
		max_z = max_node_pos.z

		trs = scene.GetNode('red_player').GetTransform()
		pos = trs.GetPos()
		rot = trs.GetRot()

		world = hg.RotationMat3(rot.x, rot.y, rot.z)
		front = hg.GetZ(world)

		active_inputs = []

		simulated_pos_forward = pos + front * (hg.time_to_sec_f(dt) * 10)
		simulated_pos_backward = pos - front * (hg.time_to_sec_f(dt) * 10)
		if (keyboard.Down(hg.K_Up)) and simulated_pos_forward.x < max_x and simulated_pos_forward.x > min_x and simulated_pos_forward.z < max_z and simulated_pos_forward.z > min_z:
			active_inputs.append("UP")
		if keyboard.Down(hg.K_Down) and simulated_pos_backward.x < max_x and simulated_pos_backward.x > min_x and simulated_pos_backward.z < max_z and simulated_pos_backward.z > min_z:
			active_inputs.append("DOWN")
		if keyboard.Down(hg.K_Right):
			active_inputs.append("RIGHT")
		if keyboard.Down(hg.K_Left):
			active_inputs.append("LEFT")

		for input_value in active_inputs:
			ProcessInputs(input_value, pos, rot, front, dt, trs)

		scene.Update(dt)

		scene.SetCurrentCamera(cam)
		vid, pass_ids = hg.SubmitSceneToPipeline(vid, scene, hg.IntRect(0, 0, res_x, res_y), True, pipeline, res, pipeline_aaa, pipeline_aaa_config, frame)
		scene.SetCurrentCamera(camera_robot)
		vid, pass_ids = hg.SubmitSceneToPipeline(vid, scene, hg.IntRect(0, 0, 512, 512), True, pipeline, res, frame_buffer.handle)

		hg.ImGuiBeginFrame(res_x, res_y, dt, mouse.GetState(), keyboard.GetState())

		hg.ImGuiSetNextWindowPos(hg.Vec2(10, 10))
		hg.ImGuiSetNextWindowSize(hg.Vec2(300, 180), hg.ImGuiCond_Once)

		if hg.ImGuiBegin('Online Robots Config'):
			was_changed_goToTarget, goToTarget = hg.ImGuiCheckbox('GoToTarget', goToTarget)
		hg.ImGuiEnd()

		if hg.ImGuiBegin("Render Robot View"):
			hg.ImGuiImage(color, hg.Vec2(512, 512))
		hg.ImGuiEnd()

		target_transform = scene.GetNode("qr_1").GetTransform()
		target_positions = [hg.Vec3(4.77, 0.53, 0.0), hg.Vec3(-2, 0.5, 3)]
		target_rotations = [hg.Vec3(0,0, math.pi/2), hg.Vec3(math.pi, math.pi/2, -math.pi/2)]

		if hg.ReadKeyboard().Key(hg.K_Space):
			target_transform.SetPos(target_positions[id_target_positions])
			target_transform.SetRot(target_rotations[id_target_positions])
			if id_target_positions >= 1:
				id_target_positions = 0
			else:
				id_target_positions += 1

		if goToTarget:
			if state == "none":
				state = "capture"
				frame_count_capture, vid = hg.CaptureTexture(vid, res, tex_color_ref, tex_readback, picture)
			elif state == "capture" and frame_count_capture <= frame:
				image = GetOpenCvImageFromPicture(picture)
				if image is not None:
					lost_timer = GoTo(pos, rot, front, image, trs, dt, lost_timer)
					state = "none"

		hg.ImGuiEndFrame(255)
		frame = hg.Frame()

		hg.UpdateWindow(win)

	cv2.waitKey(0)
	cv2.destroyAllWindows()
	hg.RenderShutdown()
	hg.DestroyWindow(win)

main()
