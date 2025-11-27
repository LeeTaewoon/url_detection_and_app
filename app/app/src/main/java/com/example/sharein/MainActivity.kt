package com.example.sharein

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.util.PatternsCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import org.json.JSONArray
import org.json.JSONObject
import androidx.compose.material3.Scaffold
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.IconButton
import androidx.compose.material3.Icon
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.Row
import androidx.compose.ui.Alignment


class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val (sharedText, sourceApp) = extractSharedText(intent)

        setContent {
            MaterialTheme {
                ShareInScreen(
                    sharedText = sharedText,
                    sourceApp = sourceApp,
                    onExtractLinks = { text, copyToClipboard ->
                        val urls = extractUrls(text)
                        if (copyToClipboard && urls.isNotEmpty()) {
                            val cb = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                            cb.setPrimaryClip(
                                ClipData.newPlainText(
                                    "urls",
                                    urls.joinToString("\n")
                                )
                            )
                            Toast.makeText(
                                this,
                                "${urls.size}개 링크 복사됨",
                                Toast.LENGTH_SHORT
                            ).show()
                        }
                        urls
                    }
                )
            }
        }
    }

    // 이미 실행 중인 상태에서 공유로 또 들어올 때 처리
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)

        val (sharedText, sourceApp) = extractSharedText(intent)

        setContent {
            MaterialTheme {
                ShareInScreen(
                    sharedText = sharedText,
                    sourceApp = sourceApp,
                    onExtractLinks = { text, copyToClipboard ->
                        val urls = extractUrls(text)
                        if (copyToClipboard && urls.isNotEmpty()) {
                            val cb = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                            cb.setPrimaryClip(
                                ClipData.newPlainText(
                                    "urls",
                                    urls.joinToString("\n")
                                )
                            )
                            Toast.makeText(
                                this,
                                "${urls.size}개 링크 복사됨",
                                Toast.LENGTH_SHORT
                            ).show()
                        }
                        urls
                    }
                )
            }
        }
    }

    /** ShareInActivity에 있던 shared text 추출 함수 */
    private fun extractSharedText(intent: Intent?): Pair<String, String?> {
        if (intent == null) return "" to null
        val action = intent.action
        val type = intent.type

        var sharedText: String? = null
        if (Intent.ACTION_SEND == action && type == "text/plain") {
            sharedText = intent.getStringExtra(Intent.EXTRA_TEXT)
        } else if (Intent.ACTION_SEND_MULTIPLE == action && type?.startsWith("text/") == true) {
            val texts = intent.getStringArrayListExtra(Intent.EXTRA_TEXT)
            sharedText = texts?.joinToString("\n")
        }

        if (sharedText.isNullOrBlank()) {
            val clip = intent.clipData
            if (clip != null && clip.itemCount > 0) {
                val sb = StringBuilder()
                for (i in 0 until clip.itemCount) {
                    val item = clip.getItemAt(i)
                    when {
                        item.text != null -> sb.appendLine(item.text)
                        item.uri != null -> readTextFromUri(item.uri)?.let { sb.appendLine(it) }
                    }
                }
                sharedText = sb.toString().trim().ifEmpty { null }
            }
        }

        val sourceApp =
            intent.`package` ?: intent.getStringExtra("android.intent.extra.PACKAGE_NAME")
        return (sharedText ?: "") to sourceApp
    }

    private fun readTextFromUri(uri: Uri?): String? {
        if (uri == null) return null
        return try {
            contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() }
        } catch (_: Exception) {
            null
        }
    }
}

/** URL만 추출: http/https 단축링크(bit.ly 등) 포함, 중복 제거 */
private fun extractUrls(text: String): List<String> {
    val m = PatternsCompat.WEB_URL.matcher(text)
    val out = mutableListOf<String>()
    while (m.find()) {
        var url = m.group() ?: continue
        url = url.trimEnd('.', ',', ';', ')', ']', '}', '\"', '\'')
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "http://$url"
        }
        out += url
    }
    return out.distinct()
}

private val http = OkHttpClient.Builder()
    .connectTimeout(15, java.util.concurrent.TimeUnit.SECONDS)
    .writeTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
    .readTimeout(240, java.util.concurrent.TimeUnit.SECONDS)
    .build()

private suspend fun postLinks(urls: List<String>, serverUrl: String): String? =
    withContext(Dispatchers.IO) {
        if (urls.isEmpty()) return@withContext null

        val json = JSONObject().apply {
            put("device", "android")
            put("links", JSONArray(urls))
            put("timestamp", System.currentTimeMillis())
        }

        val body = RequestBody.create(
            "application/json; charset=utf-8".toMediaType(),
            json.toString()
        )

        val req = Request.Builder()
            .url(serverUrl)
            .post(body)
            .build()

        try {
            http.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@withContext null
                val responseText = resp.body?.string() ?: return@withContext null
                val jsonResp = JSONObject(responseText)

                val results = jsonResp.optJSONArray("results")
                if (results != null && results.length() > 0) {
                    val first = results.getJSONObject(0)
                    return@withContext first.optString("final_label", null)
                }
                null
            }
        } catch (_: Exception) {
            null
        }
    }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ShareInScreen(
    sharedText: String,
    sourceApp: String?,
    onExtractLinks: (text: String, copyToClipboard: Boolean) -> List<String>
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var urls by remember { mutableStateOf<List<String>>(emptyList()) }

    // 화면에 들어오면 자동으로 링크 추출
    LaunchedEffect(sharedText) {
        urls = onExtractLinks(sharedText, false)
    }
    var resultLabel by remember { mutableStateOf<String?>(null) }

    // SharedPreferences
    val prefs = remember {
        context.getSharedPreferences("stshield_prefs", Context.MODE_PRIVATE)
    }

    // 서버 URL 상태 (기본값은 네가 쓰던 값)
    var serverUrl by remember { mutableStateOf("http://192.168.0.2:5050/receive") }

    // 앱 진입 시 저장된 URL 불러오기
    LaunchedEffect(Unit) {
        val saved = prefs.getString("server_url", null)
        if (!saved.isNullOrBlank()) {
            serverUrl = saved
        }
    }

    // URL 설정 다이얼로그 표시 여부
    var showServerUrlDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Image(
                            painter = painterResource(id = R.drawable.stshield_logo_thick),
                            contentDescription = "STShield Logo",
                            modifier = Modifier
                                .size(28.dp)            // 로고 크기
                                .padding(end = 8.dp)    // 텍스트와 간격
                        )
                        Text("STShield")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFFFAFAFA),
                    titleContentColor = Color.Black
                ),
                actions = {
                    IconButton(onClick = { showServerUrlDialog = true }) {
                        Icon(
                            imageVector = Icons.Default.Menu,
                            contentDescription = "서버 URL 설정"
                        )
                    }
                }
            )
        }
    ) { innerPadding ->

        Surface(
            color = Color(0xFFFAFAFA),
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {

                // 🔹 공유된 문자/앱 정보
                Text(
                    "받은 메시지:",
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Bold
                )
                Spacer(Modifier.height(8.dp))
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = Color(0xFFF4F4F4)   // 연한 회색 (가독성 Good)
                    ),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                    border = BorderStroke(1.dp, Color(0xFFDDDDDD))
                ) {
                    Text(
                        text = if (sharedText.isBlank()) "(공유된 텍스트가 없습니다)" else sharedText,
                        style = MaterialTheme.typography.bodyLarge,
                        modifier = Modifier.padding(16.dp)
                    )
                }
                Spacer(Modifier.height(16.dp))

                // 추출된 URL 리스트 표시
                if (urls.isNotEmpty()) {
                    Spacer(Modifier.height(12.dp))
                    Text("추출된 링크:", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(6.dp))
                    urls.forEach { u ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp),
                            shape = RoundedCornerShape(10.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = Color(0xFFF4F4F4) // 연한 회색 박스
                            ),
                            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                            border = BorderStroke(1.dp, Color(0xFFDDDDDD))
                        ) {
                            Text(
                                text = u,
                                style = MaterialTheme.typography.bodyLarge,
                                modifier = Modifier.padding(12.dp)
                            )
                        }
                    }
                }

                Spacer(Modifier.height(16.dp))

                // PC로 전송 및 검사
                Button(
                    onClick = {
                        val toSend =
                            if (urls.isNotEmpty()) urls else extractUrls(sharedText)
                        scope.launch {
                            resultLabel = "검사 중..."
                            val label = postLinks(toSend, serverUrl)
                            resultLabel = when (label) {
                                "정상" -> "✅ 결과: 정상 URL로 판단되었습니다"
                                "비정상" -> "⚠️ 결과: 악성 URL로 판단되었습니다"
                                null -> "❌ 서버 응답을 받지 못했습니다"
                                else -> "결과: $label"
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFF002B7F),   // 남색
                        contentColor = Color.White
                    )
                ) {
                    Text("PC로 전송 및 검사", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                }


                // 검사 결과 문구
                if (!resultLabel.isNullOrBlank()) {
                    Spacer(Modifier.height(16.dp))

                    // 결과 내용에 따라 색상 다르게
                    val isMalicious =
                        resultLabel!!.contains("악성") || resultLabel!!.contains("비정상")
                    val bgColor = if (isMalicious) Color(0xFFFFEBEE) else Color(0xFFE8F5E9)   // 빨간/초록 계열 배경
                    val textColor = if (isMalicious) Color(0xFFD32F2F) else Color(0xFF2E7D32) // 빨간/초록 글자

                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = bgColor),
                        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                    ) {
                        Text(
                            text = resultLabel!!,
                            style = MaterialTheme.typography.bodyLarge.copy(
                                color = textColor,
                                fontWeight = FontWeight.SemiBold
                            ),
                            modifier = Modifier.padding(16.dp)
                        )
                    }
                }
            }
        }

        // 서버 URL 설정 다이얼로그
        if (showServerUrlDialog) {
            AlertDialog(
                onDismissRequest = { showServerUrlDialog = false },
                title = { Text("서버 URL 설정") },
                text = {
                    OutlinedTextField(
                        value = serverUrl,
                        onValueChange = { serverUrl = it },
                        singleLine = true,
                        label = { Text("서버 URL (PC)") },
                        modifier = Modifier.fillMaxWidth()
                    )
                },
                confirmButton = {
                    TextButton(onClick = {
                        // URL 저장
                        prefs.edit()
                            .putString("server_url", serverUrl)
                            .apply()
                        showServerUrlDialog = false
                    }) {
                        Text("확인")
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showServerUrlDialog = false }) {
                        Text("취소")
                    }
                }
            )
        }
    }
}

