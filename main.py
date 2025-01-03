import harfang as hg
import socket
import threading
import pickle
import time
from utils import RangeAdjust
from name_tag import DrawNameTag

#Network Config
UDP_IP = "127.0.0.1"
UDP_PORT = 5005

#Socket Init
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

#Global Variables
MESSAGE = [0, 0, 0, 0, 0, 0, 0, 0]
players = []
lerped_players, old_players, next_players = [], [], []
send_id = 0
time_deltas = [0.1]
global_time_end = global_last_packet = 0

#Network Functions
def HandleSend():
	global MESSAGE, send_id
	while True:
		sock.sendto(pickle.dumps(MESSAGE), (UDP_IP, UDP_PORT))
		send_id += 1
		time.sleep(1/60)

def HandleReceive():
	global players, old_players, next_players, global_time_end, global_last_packet, time_deltas
	while True:
		data, _ = sock.recvfrom(1024)
		decoded_data = pickle.loads(data)
		if decoded_data[0] == 1:
			UpdatePlayers(decoded_data[1])

def UpdatePlayers(new_data):
	global players, old_players, global_last_packet, time_deltas
	timestamp = time.time()
	if timestamp < global_time_end and global_time_end != 0:
		next_players = new_data + [timestamp]
	else:
		if len(players) == len(lerped_players):
			old_players = lerped_players.copy()
		else:
			old_players = players.copy()
		players = new_data + [timestamp]
	record_time_delta(timestamp)

def record_time_delta(current_time):
	global global_last_packet, time_deltas
	if global_last_packet != 0:
		time_deltas.insert(0, current_time - global_last_packet)
		if len(time_deltas) > 20:
			time_deltas.pop()
	global_last_packet = current_time

#Init threads
threading.Thread(target=HandleSend).start()
threading.Thread(target=HandleReceive).start()

#Init Harfang
hg.InputInit()
hg.WindowSystemInit()

res_x, res_y = 1280, 720
win = hg.RenderInit('3D Server - Client Scene', res_x, res_y, hg.RF_VSync | hg.RF_MSAA4X)

pipeline = hg.CreateForwardPipeline()
res = hg.PipelineResources()

hg.AddAssetsFolder("server_client_demo_compiled")
hg.ImGuiInit(10, hg.LoadProgramFromAssets('core/shader/imgui'), hg.LoadProgramFromAssets('core/shader/imgui_image'))
line_shader = hg.LoadProgramFromAssets('core/shader/white')
name_shader = hg.LoadProgramFromAssets('core/shader/grey')
font = hg.LoadFontFromAssets('font/ticketing.ttf', 96)
font_prg = hg.LoadProgramFromAssets('core/shader/font')
text_uniform_values = [hg.MakeUniformSetValue('u_color', hg.Vec4(1, 1, 1))]
text_render_state = hg.ComputeRenderState(hg.BM_Alpha, hg.DT_Always, hg.FC_Disabled)

vtx_layout = hg.VertexLayout()
vtx_layout.Begin()
vtx_layout.Add(hg.A_Position, 3, hg.AT_Float)
vtx_layout.End()

# Load Scene
scene = hg.Scene()
hg.LoadSceneFromAssets("level_1_full.scn", scene, res, hg.GetForwardPipelineInfo())
cam = scene.GetNode('Camera')
cam_rot = scene.GetNode('camrotation')

pipeline_aaa_config = hg.ForwardPipelineAAAConfig()
pipeline_aaa = hg.CreateForwardPipelineAAAFromAssets("core", pipeline_aaa_config, hg.BR_Equal, hg.BR_Equal)
pipeline_aaa_config.sample_count = 1
pipeline_aaa_config.motion_blur = 0

keyboard = hg.Keyboard()
mouse = hg.Mouse()

#Main Loop
frame = 0
show_lerp = show_pred = show_real = True
auto_move = False
vid_scene_opaque = 0
vtx_2, vtx_4 = hg.Vertices(vtx_layout, 2), hg.Vertices(vtx_layout, 4)

def HandlePlayerLogic():
	global players, lerped_players
	new_lerped_players = []

	for pinstance in players:
		ProcessPlayerInstance(pinstance, new_lerped_players)

	lerped_players = new_lerped_players

def ProcessPlayerInstance(pinstance, new_lerped_players):
	global players, old_players

	player_transform = pinstance[0][0].GetTransform()
	player_nolerp_transform = pinstance[0][1].GetTransform()
	player_pred_transform = pinstance[0][2].GetTransform()
	player_id = pinstance[1]

	player_updated_pos = hg.Vec3(players[player_id][0], players[player_id][1], players[player_id][2])
	player_old_pos = hg.Vec3(old_players[player_id][0], old_players[player_id][1], old_players[player_id][2])

	adjusted_time = RangeAdjust(time.time(), players[-1], global_time_end, 0, 1)
	wanted_pos = hg.Lerp(player_old_pos, player_updated_pos, adjusted_time)

	if show_lerp:
		player_transform.SetPos(wanted_pos)
	else:
		player_transform.SetPos(hg.Vec3(-100, -100, -100))

	#Prediction
	pos_dif = player_updated_pos - player_old_pos
	predicted_pos = player_updated_pos + (pos_dif * adjusted_time)

	if show_pred:
		player_pred_transform.SetPos(predicted_pos)
	else:
		player_pred_transform.SetPos(hg.Vec3(-100, -100, -100))

	#Real Position
	if show_real:
		player_nolerp_transform.SetPos(player_updated_pos)
	else:
		player_nolerp_transform.SetPos(hg.Vec3(-100, -100, -100))

def DisplayUI():
	hg.ImGuiBeginFrame(res_x, res_y, hg.TickClock(), mouse.GetState(), keyboard.GetState())

	if hg.ImGuiBegin('Online Robots Config'):
		global show_lerp, show_pred, show_real, auto_move
		show_lerp = hg.ImGuiCheckbox('Show Linear Interpolation', show_lerp)[1]
		show_pred = hg.ImGuiCheckbox('Show Prediction', show_pred)[1]
		show_real = hg.ImGuiCheckbox('Show Real Position', show_real)[1]
		auto_move = hg.ImGuiCheckbox('Automatic Robot Movement', auto_move)[1]

	hg.ImGuiEnd()
	hg.ImGuiEndFrame(255)

def UpdateScene(dt):
	global MESSAGE
	trs = scene.GetNode('red_player').GetTransform()
	pos = trs.GetPos()
	rot = trs.GetRot()

	MESSAGE = [0, pos.x, pos.y, pos.z, rot.x, rot.y, rot.z, send_id]
	world = hg.RotationMat3(rot.x, rot.y, rot.z)
	front = hg.GetZ(world)

	simulated_pos_forward = pos + front * (hg.time_to_sec_f(dt) * 10)
	simulated_pos_backward = pos - front * (hg.time_to_sec_f(dt) * 10)

	DrawNameTag(vtx_2, vtx_4, pos, line_shader, name_shader, vid_scene_opaque, "Local", font, font_prg,
				text_uniform_values, text_render_state, cam.GetTransform().GetWorld())

	if (keyboard.Down(hg.K_Up) or auto_move):
		trs.SetPos(simulated_pos_forward)
	if keyboard.Down(hg.K_Down):
		trs.SetPos(simulated_pos_backward)
	if keyboard.Down(hg.K_Right) or auto_move:
		trs.SetRot(hg.Vec3(rot.x, rot.y + hg.time_to_sec_f(dt), rot.z))
	if keyboard.Down(hg.K_Left):
		trs.SetRot(hg.Vec3(rot.x, rot.y - hg.time_to_sec_f(dt), rot.z))

while not hg.ReadKeyboard().Key(hg.K_Escape) and hg.IsWindowOpen(win):
	dt = hg.TickClock()
	keyboard.Update()
	mouse.Update()

	UpdateScene(dt)
	HandlePlayerLogic()

	scene.Update(dt)
	vid, pass_ids = hg.SubmitSceneToPipeline(0, scene, hg.IntRect(0,0,res_x,res_y), True, pipeline, res)
	vid_scene_opaque = hg.GetSceneForwardPipelinePassViewId(pass_ids, hg.SFPP_Opaque)


	DisplayUI()

	frame = hg.Frame()
	hg.UpdateWindow(win)

hg.RenderShutdown()
hg.DestroyWindow(win)
