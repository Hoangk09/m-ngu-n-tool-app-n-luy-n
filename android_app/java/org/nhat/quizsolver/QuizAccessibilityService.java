package org.nhat.quizsolver;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.accessibilityservice.GestureDescription;
import android.content.Intent;
import android.graphics.Path;
import android.graphics.Rect;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.ArrayList;
import java.util.List;

/**
 * Accessibility Service for Quiz Solver
 * Reads UI elements from Ôn Luyện app and performs auto-clicks
 */
public class QuizAccessibilityService extends AccessibilityService {

    private static final String TAG = "QuizSolver";
    private static final String ONLUYEN_PACKAGE = "vn.onluyen.app";

    // Singleton instance
    private static QuizAccessibilityService instance;

    // Callback interface
    public interface QuizCallback {
        void onQuestionFound(String question, List<String> options);

        void onAnswerClicked(String letter);

        void onError(String message);
    }

    private QuizCallback callback;
    private Handler mainHandler;
    private boolean isEnabled = false;

    // Store found elements
    private String lastQuestion = "";
    private List<AnswerOption> lastOptions = new ArrayList<>();

    public static class AnswerOption {
        public String letter;
        public String text;
        public Rect bounds;

        public AnswerOption(String letter, String text, Rect bounds) {
            this.letter = letter;
            this.text = text;
            this.bounds = bounds;
        }
    }

    public static QuizAccessibilityService getInstance() {
        return instance;
    }

    public static boolean isServiceEnabled() {
        return instance != null && instance.isEnabled;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        mainHandler = new Handler(Looper.getMainLooper());
        Log.i(TAG, "Service created");
    }

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();

        AccessibilityServiceInfo info = new AccessibilityServiceInfo();
        info.eventTypes = AccessibilityEvent.TYPES_ALL_MASK;
        info.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC;
        info.flags = AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                | AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
                | AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS;
        info.notificationTimeout = 100;

        setServiceInfo(info);
        isEnabled = true;

        Log.i(TAG, "Service connected and configured");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event == null)
            return;

        String packageName = event.getPackageName() != null ? event.getPackageName().toString() : "";

        // Only process Ôn Luyện app events
        if (!packageName.contains("onluyen") && !packageName.contains("ONLUYEN")) {
            return;
        }

        int eventType = event.getEventType();

        // Process on content change or window change
        if (eventType == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED ||
                eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {

            // Scan for quiz content
            scanForQuizContent();
        }
    }

    @Override
    public void onInterrupt() {
        Log.w(TAG, "Service interrupted");
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        instance = null;
        isEnabled = false;
        Log.i(TAG, "Service destroyed");
    }

    /**
     * Set callback for quiz events
     */
    public void setCallback(QuizCallback callback) {
        this.callback = callback;
    }

    /**
     * Scan current screen for quiz content
     */
    public void scanForQuizContent() {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) {
            Log.d(TAG, "No root node available");
            return;
        }

        try {
            // Find question text - usually the longest text or in a specific container
            String question = findQuestionText(root);

            // Find answer options
            List<AnswerOption> options = findAnswerOptions(root);

            if (question != null && !question.isEmpty() && !options.isEmpty()) {
                lastQuestion = question;
                lastOptions = options;

                Log.i(TAG, "Found question: " + question.substring(0, Math.min(50, question.length())) + "...");
                Log.i(TAG, "Found " + options.size() + " options");

                if (callback != null) {
                    List<String> optionTexts = new ArrayList<>();
                    for (AnswerOption opt : options) {
                        optionTexts.add(opt.letter + ". " + opt.text);
                    }
                    callback.onQuestionFound(question, optionTexts);
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error scanning content: " + e.getMessage());
        } finally {
            root.recycle();
        }
    }

    /**
     * Find question text in the UI tree
     */
    private String findQuestionText(AccessibilityNodeInfo node) {
        if (node == null)
            return null;

        String result = null;
        int maxLength = 0;

        // Recursively search all nodes
        List<AccessibilityNodeInfo> textNodes = new ArrayList<>();
        findAllTextNodes(node, textNodes);

        for (AccessibilityNodeInfo textNode : textNodes) {
            CharSequence text = textNode.getText();
            if (text != null) {
                String str = text.toString().trim();

                // Skip short texts and answer options
                if (str.length() > 30 &&
                        !str.matches("^[A-Da-d]\\..*") &&
                        !str.toLowerCase().contains("đáp án") &&
                        !str.toLowerCase().contains("tiếp") &&
                        str.length() > maxLength) {

                    result = str;
                    maxLength = str.length();
                }
            }
        }

        return result;
    }

    /**
     * Find answer options (A, B, C, D)
     */
    private List<AnswerOption> findAnswerOptions(AccessibilityNodeInfo node) {
        List<AnswerOption> options = new ArrayList<>();
        if (node == null)
            return options;

        List<AccessibilityNodeInfo> textNodes = new ArrayList<>();
        findAllTextNodes(node, textNodes);

        for (AccessibilityNodeInfo textNode : textNodes) {
            CharSequence text = textNode.getText();
            if (text != null) {
                String str = text.toString().trim();

                // Match patterns like "A. answer", "A) answer", "A answer"
                if (str.matches("^[A-Da-d][.\\)\\s].*") && str.length() > 2) {
                    String letter = str.substring(0, 1).toUpperCase();
                    String answerText = str.substring(2).trim();

                    Rect bounds = new Rect();
                    textNode.getBoundsInScreen(bounds);

                    options.add(new AnswerOption(letter, answerText, bounds));
                    Log.d(TAG, "Found option: " + letter + " - "
                            + answerText.substring(0, Math.min(30, answerText.length())));
                }
            }
        }

        return options;
    }

    /**
     * Recursively find all text nodes
     */
    private void findAllTextNodes(AccessibilityNodeInfo node, List<AccessibilityNodeInfo> result) {
        if (node == null)
            return;

        if (node.getText() != null && node.getText().length() > 0) {
            result.add(node);
        }

        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                findAllTextNodes(child, result);
            }
        }
    }

    /**
     * Click on a specific answer option
     */
    public boolean clickAnswer(String letter) {
        for (AnswerOption option : lastOptions) {
            if (option.letter.equalsIgnoreCase(letter)) {
                return clickAtBounds(option.bounds);
            }
        }

        Log.w(TAG, "Answer " + letter + " not found in saved options, rescanning...");

        // Try rescanning
        scanForQuizContent();

        for (AnswerOption option : lastOptions) {
            if (option.letter.equalsIgnoreCase(letter)) {
                return clickAtBounds(option.bounds);
            }
        }

        Log.e(TAG, "Could not find answer " + letter);
        return false;
    }

    /**
     * Click at center of bounds
     */
    public boolean clickAtBounds(Rect bounds) {
        if (bounds == null)
            return false;

        int x = bounds.centerX();
        int y = bounds.centerY();

        return clickAt(x, y);
    }

    /**
     * Perform click at coordinates using gesture
     */
    public boolean clickAt(int x, int y) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) {
            Log.e(TAG, "Gestures require Android 7.0+");
            return false;
        }

        Log.i(TAG, "Clicking at (" + x + ", " + y + ")");

        Path clickPath = new Path();
        clickPath.moveTo(x, y);

        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(new GestureDescription.StrokeDescription(clickPath, 0, 50));

        return dispatchGesture(builder.build(), new GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                Log.i(TAG, "Click completed");
                if (callback != null) {
                    mainHandler.post(() -> callback.onAnswerClicked(""));
                }
            }

            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                Log.w(TAG, "Click cancelled");
            }
        }, null);
    }

    /**
     * Perform swipe gesture
     */
    public boolean swipe(int startX, int startY, int endX, int endY, int durationMs) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) {
            return false;
        }

        Path swipePath = new Path();
        swipePath.moveTo(startX, startY);
        swipePath.lineTo(endX, endY);

        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(new GestureDescription.StrokeDescription(swipePath, 0, durationMs));

        return dispatchGesture(builder.build(), null, null);
    }

    /**
     * Go to next question (swipe left or click next button)
     */
    public void goNextQuestion() {
        // Try to find and click "Tiếp" button first
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root != null) {
            try {
                List<AccessibilityNodeInfo> nodes = root.findAccessibilityNodeInfosByText("Tiếp");
                if (nodes != null && !nodes.isEmpty()) {
                    for (AccessibilityNodeInfo node : nodes) {
                        if (node.isClickable()) {
                            node.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                            Log.i(TAG, "Clicked 'Tiếp' button");
                            return;
                        }

                        // Try clicking parent
                        AccessibilityNodeInfo parent = node.getParent();
                        if (parent != null && parent.isClickable()) {
                            parent.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                            Log.i(TAG, "Clicked parent of 'Tiếp' button");
                            return;
                        }
                    }
                }
            } finally {
                root.recycle();
            }
        }

        // Fallback: swipe left
        int screenWidth = getResources().getDisplayMetrics().widthPixels;
        int screenHeight = getResources().getDisplayMetrics().heightPixels;

        swipe(
                (int) (screenWidth * 0.8), screenHeight / 2,
                (int) (screenWidth * 0.2), screenHeight / 2,
                300);

        Log.i(TAG, "Swiped left to next question");
    }

    /**
     * Get the current question and options
     */
    public String getLastQuestion() {
        return lastQuestion;
    }

    public List<AnswerOption> getLastOptions() {
        return new ArrayList<>(lastOptions);
    }

    /**
     * Force rescan
     */
    public void rescan() {
        scanForQuizContent();
    }
}
